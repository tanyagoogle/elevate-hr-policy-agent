#!/usr/bin/env python3
"""Vertex AI Search verification client (Track A / RAG).

Sanity-check the RAG data store before wiring it into the agent: confirm semantic
retrieval quality and that citation links come back.

Live mode:
    uv run python rag/verify-rag-search.py --query "outpatient sick leave"
    # uses GOOGLE_CLOUD_PROJECT / VERTEX_AI_SEARCH_ENGINE_ID from the environment

Offline mock mode (no GCP needed, for local dev of the parser):
    uv run python rag/verify-rag-search.py --mock --query "sick leave"
"""
import argparse
import os
import sys

from google.api_core.client_options import ClientOptions

try:
    from google.cloud import discoveryengine_v1 as discoveryengine
except ImportError:
    discoveryengine = None


# Offline snippets mirror the real handbook facts (keys are matched as substrings).
MOCK_DATABASE = {
    "sick": {
        "title": "Handbook Section 1.1 — Outpatient Sick & Hospitalization Leave",
        "snippet": "Eligible employees receive up to 14 days of paid outpatient sick leave per calendar year at 100% of base salary, plus an additional 46 work days of hospitalization leave. If you are sick for more than two work days, submit an MC via WorkWeek within 48 hours.",
        "link": "https://hr-portal.altostrat.com/handbook#1.1-sick-hospitalization-leave",
    },
    "vacation": {
        "title": "Handbook Section 1.2 — Paid Vacation Leave",
        "snippet": "Accrual tiers: 1-6 years = 20 days, 7-10 years = 21 days, 11+ years = 22 days. Shift workers book by actual shift hours; a vacation day is an 8-hour block, so a 12-hour shift requires 1.5 vacation days.",
        "link": "https://hr-portal.altostrat.com/handbook#1.2-vacation-leave",
    },
    "ramp": {
        "title": "Handbook Section 2.3 — Ramp-Back Time",
        "snippet": "After at least 10 consecutive weeks of parental/baby-bonding leave, take up to 2 weeks of paid ramp-back time, working a minimum of 50% of normal weekly hours while receiving 100% of normal salary.",
        "link": "https://hr-portal.altostrat.com/handbook#2.3-ramp-back-time",
    },
    "host": {
        "title": "Handbook Section 4.3 — Lodging & Transportation",
        "snippet": "Staying with a friend or relative allows a host gift of up to US $50 per day with valid receipts. Cash or gift-card host gifts are strictly prohibited.",
        "link": "https://hr-portal.altostrat.com/handbook#4.3-lodging-transportation",
    },
    "salon": {
        "title": "Handbook Section 5.2 / 14 — Business Courtesies",
        "snippet": "Business courtesies must never involve gambling, adult entertainment (strip clubs, hostess bars, room salons), cash, or cash equivalents (gift cards). Prohibited regardless of value.",
        "link": "https://hr-portal.altostrat.com/handbook#5.2-gifts-entertainment",
    },
}


def query_vertex_search(project_id, location, engine_id, query_text):
    if not discoveryengine:
        print("[ERROR] uv sync (installs google-cloud-discoveryengine)")
        sys.exit(1)

    print(f"\nQuerying engine '{engine_id}' in project '{project_id}' ({location})")
    print(f"Query: {query_text!r}\n")

    client_options = (
        ClientOptions(api_endpoint=f"{location}-discoveryengine.googleapis.com")
        if location != "global"
        else None
    )
    client = discoveryengine.SearchServiceClient(client_options=client_options)
    serving_config = (
        f"projects/{project_id}/locations/{location}/collections/default_collection"
        f"/engines/{engine_id}/servingConfigs/default_search"
    )
    content_spec = discoveryengine.SearchRequest.ContentSearchSpec(
        extractive_content_spec=discoveryengine.SearchRequest.ContentSearchSpec.ExtractiveContentSpec(
            max_extractive_answer_count=3, max_extractive_segment_count=3
        )
    )
    request = discoveryengine.SearchRequest(
        serving_config=serving_config, query=query_text, page_size=3, content_search_spec=content_spec
    )
    try:
        response = client.search(request)
    except Exception as e:  # noqa: BLE001
        print(f"[ERROR] {e}")
        print("Check: gcloud auth application-default login; roles/discoveryengine.viewer; engine id.")
        sys.exit(1)

    found = False
    for i, result in enumerate(response.results, 1):
        found = True
        d = result.document.derived_struct_data
        print(f"[{i}] {d.get('title', 'Untitled')}")
        print(f"    link: {d.get('link', '(none)')}")
    if not found:
        print("[INFO] 0 results.")


def run_mock(query_text):
    print(f"\n--- OFFLINE MOCK MODE ---\nQuery: {query_text!r}\n")
    q = query_text.lower()
    for key, match in MOCK_DATABASE.items():
        if key in q:
            print(f"[1] {match['title']}")
            print(f"    link: {match['link']}")
            print(f"    excerpt: {match['snippet']}")
            print("\n[PASS] retrieved a grounded snippet + citation link.")
            return
    print("[INFO] 0 matches (query outside the mock corpus).")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Vertex AI Search verification client")
    parser.add_argument("--project", default=os.getenv("GOOGLE_CLOUD_PROJECT"))
    parser.add_argument("--location", default=os.getenv("VERTEX_AI_SEARCH_LOCATION", "global"))
    parser.add_argument("--engine-id", default=os.getenv("VERTEX_AI_SEARCH_ENGINE_ID", "hr-policies-lab-engine"))
    parser.add_argument("--query", required=True)
    parser.add_argument("--mock", action="store_true", help="run offline with the built-in mock corpus")
    args = parser.parse_args()

    if args.mock:
        run_mock(args.query)
    elif not args.project:
        print("[ERROR] --project or GOOGLE_CLOUD_PROJECT required (or use --mock).")
        sys.exit(1)
    else:
        query_vertex_search(args.project, args.location, args.engine_id, args.query)
