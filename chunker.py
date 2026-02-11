#!/usr/bin/env python3
"""
Community JSON → text chunks for RAG embedding.

Each community profile is split into semantic chunks by section.
Each chunk includes community name, section label, URL reference,
and visualization metadata describing how the data is displayed
on Calgary Pulse (component type, chart type, data keys).
"""

import json
from pathlib import Path


PULSE_BASE_URL = "https://calgarypulse.ca/communities"


def format_currency(value):
    """Format a number as currency."""
    if value is None:
        return "N/A"
    return f"${value:,.0f}"


def format_pct(value):
    """Format a percentage."""
    if value is None:
        return "N/A"
    return f"{value:+.1f}%" if value >= 0 else f"{value:.1f}%"


def chunk_hero(data, slug, name):
    """Overview/hero section."""
    hero = data.get("hero", {})
    desc = data.get("description", "")
    sector = data.get("sector", "")
    district = data.get("creb_district", "")
    distance = data.get("distance_to_downtown_km")

    text = f"{name} community overview. "
    text += f"Located in {sector} sector, CREB district: {district}. "
    if distance:
        text += f"{distance:.1f} km from downtown. "
    if hero.get("population"):
        text += f"Population: {hero['population']:,}. "
    if hero.get("safety_percentile") is not None:
        text += f"Safety percentile: {hero['safety_percentile']}/100. "
    if hero.get("avg_value"):
        text += f"Average assessed home value: {format_currency(hero['avg_value'])}. "
    if desc:
        text += desc

    return {
        "id": f"{slug}-overview",
        "community": slug,
        "section": "overview",
        "url": f"{PULSE_BASE_URL}/{slug}",
        "text": text,
        "viz": [
            {
                "type": "stat-cards",
                "component": "HeroCards",
                "data_keys": ["hero.population", "hero.safety_percentile", "hero.avg_value", "housing.value_vs_city"],
                "description": "Three stat cards: Population, Safety Score (color-coded), Assessed Value"
            }
        ]
    }


def chunk_safety(data, slug, name):
    """Safety and crime section."""
    safety = data.get("safety", {})
    if not safety:
        return None

    crime = safety.get("crime", {})
    disorder = safety.get("disorder", {})
    breakdown = safety.get("breakdown", {})

    text = f"{name} safety and crime data. "
    text += f"Safety percentile: {safety.get('percentile', 'N/A')}/100 "
    text += f"({safety.get('percentile_label', '')}). "

    if crime:
        text += f"Crime incidents (latest quarter): {crime.get('count', 'N/A'):,}, "
        text += f"{crime.get('per_1000', 'N/A')} per 1,000 residents "
        text += f"(city average: {crime.get('city_avg_per_1000', 'N/A')}). "
        if crime.get("yoy_pct") is not None:
            text += f"Year-over-year change: {format_pct(crime['yoy_pct'])}. "

    if breakdown:
        prop = breakdown.get("property", {})
        violent = breakdown.get("violent", {})
        if prop.get("pct") and violent.get("pct"):
            text += f"Breakdown: {prop['pct']}% property crime, {violent['pct']}% violent crime. "

    if disorder:
        text += f"Disorder calls: {disorder.get('count', 'N/A'):,}, "
        text += f"{disorder.get('per_1000', 'N/A')} per 1,000 "
        text += f"(city average: {disorder.get('city_avg_per_1000', 'N/A')}). "

    # Trend summary
    trend = safety.get("trend", [])
    if len(trend) >= 2:
        first = trend[0]
        last = trend[-1]
        text += f"Crime trend: {first['quarter']} had {first['crime']} incidents, "
        text += f"{last['quarter']} had {last['crime']} incidents. "

    return {
        "id": f"{slug}-safety",
        "community": slug,
        "section": "safety",
        "url": f"{PULSE_BASE_URL}/{slug}#safety",
        "text": text,
        "viz": [
            {
                "type": "stat-cards",
                "component": "SafetyStats",
                "data_keys": ["safety.crime.count", "safety.crime.yoy_pct", "safety.crime.per_1000",
                              "safety.crime.city_avg_per_1000", "safety.disorder.count",
                              "safety.disorder.per_1000", "safety.disorder.city_avg_per_1000"],
                "description": "Two metric cards: Crime incidents with YoY and per-1000 rate vs city avg, Disorder calls with same"
            },
            {
                "type": "line-chart",
                "component": "CrimeTrendChart",
                "data_keys": ["safety.trend"],
                "series": [
                    {"key": "crime", "label": "Crime Incidents"},
                    {"key": "disorder", "label": "Disorder Calls"}
                ],
                "x_axis": "quarter",
                "description": "Dual-line chart showing crime and disorder trends over 8 quarters with linear regression trend line"
            },
            {
                "type": "stat-cards",
                "component": "CrimeBreakdown",
                "data_keys": ["safety.breakdown.property", "safety.breakdown.violent"],
                "description": "Two cards: Property crime vs Violent crime counts and percentages"
            },
            {
                "type": "stat-grid",
                "component": "DisorderBreakdown",
                "data_keys": ["safety.disorder_breakdown"],
                "description": "Grid of disorder categories (disturbances, suspicious, welfare, other) with counts and percentages"
            }
        ]
    }


def chunk_housing(data, slug, name):
    """Housing and assessments section."""
    housing = data.get("housing", {})
    if not housing:
        return None

    text = f"{name} housing data. "
    text += f"Average assessed value: {format_currency(housing.get('assessed_value'))}. "
    if housing.get("value_vs_city") is not None:
        text += f"Compared to city median: {format_pct(housing['value_vs_city'])}. "
    text += f"Total properties: {housing.get('property_count', 'N/A'):,}. "

    by_type = housing.get("assessed_by_type", {})
    for ptype, info in by_type.items():
        if info.get("count", 0) > 0:
            label = ptype.replace("_", " ").title()
            text += f"{label}: {format_currency(info['value'])} avg ({info['count']:,} properties"
            if info.get("value_yoy") is not None:
                text += f", {format_pct(info['value_yoy'])} YoY"
            text += "). "

    benchmarks = housing.get("district_benchmarks", {})
    if benchmarks.get("date"):
        district = housing.get("district", "")
        text += f"District ({district}) benchmark prices as of {benchmarks['date']}: "
        for ptype in ["detached", "semi_detached", "row", "apartment"]:
            if benchmarks.get(ptype):
                label = ptype.replace("_", " ").title()
                text += f"{label}: {format_currency(benchmarks[ptype])}, "

    return {
        "id": f"{slug}-housing",
        "community": slug,
        "section": "housing",
        "url": f"{PULSE_BASE_URL}/{slug}#housing",
        "text": text,
        "viz": [
            {
                "type": "stat-cards",
                "component": "HousingAssessments",
                "data_keys": ["housing.assessed_value", "housing.value_vs_city", "housing.property_count"],
                "description": "Summary card: average assessed value, comparison to city median, total properties"
            },
            {
                "type": "stat-grid",
                "component": "HousingByType",
                "data_keys": ["housing.assessed_by_type"],
                "description": "Grid of property types (Detached, Semi, Row, Apartment) each showing avg value, count, and YoY change"
            },
            {
                "type": "stat-grid",
                "component": "DistrictBenchmarks",
                "data_keys": ["housing.district_benchmarks"],
                "description": "District benchmark prices by property type with YoY changes"
            }
        ]
    }


def chunk_311(data, slug, name):
    """311 service requests section."""
    sr = data.get("service_requests_311", {})
    if not sr:
        return None

    text = f"{name} 311 service requests. "
    text += f"Total requests (24 months): {sr.get('total', 'N/A'):,}. "

    top = sr.get("top_categories", [])
    if top:
        text += "Top categories: "
        for cat in top:
            text += f"{cat['category']} ({cat['count']:,}, {format_pct(cat.get('yoy_pct', 0))} YoY), "
        text = text.rstrip(", ") + ". "

    return {
        "id": f"{slug}-311",
        "community": slug,
        "section": "311-service-requests",
        "url": f"{PULSE_BASE_URL}/{slug}#311",
        "text": text,
        "viz": [
            {
                "type": "horizontal-bar",
                "component": "ServiceRequests311Section",
                "data_keys": ["service_requests_311.total", "service_requests_311.top_categories"],
                "description": "Horizontal bar chart of top 5 request categories with counts and YoY change badges"
            },
            {
                "type": "line-chart",
                "component": "ServiceRequestsTrend",
                "data_keys": ["service_requests_311.trend"],
                "series": [{"key": "count", "label": "Monthly Requests"}],
                "x_axis": "date",
                "description": "24-month line chart of monthly request counts with linear regression trend line"
            }
        ]
    }


def chunk_schools(data, slug, name):
    """Schools section."""
    schools = data.get("schools", {})
    if not schools or schools.get("count", 0) == 0:
        return None

    text = f"{name} schools. "
    text += f"{schools['count']} schools in the community. "
    if schools.get("avg_rating"):
        text += f"Average Fraser Institute rating: {schools['avg_rating']}/10 "
        text += f"({schools.get('rated_count', 0)} rated). "

    for school in schools.get("list", []):
        text += f"{school['name']} ({school['board']}, {school['level']}"
        if school.get("rating"):
            text += f", rating: {school['rating']}/10"
        text += "). "

    return {
        "id": f"{slug}-schools",
        "community": slug,
        "section": "schools",
        "url": f"{PULSE_BASE_URL}/{slug}#schools",
        "text": text,
        "viz": [
            {
                "type": "list",
                "component": "SchoolList",
                "data_keys": ["schools.list", "schools.count", "schools.avg_rating"],
                "description": "Ordered list of schools with board, grade level, and Fraser Institute rating (0-10 scale)"
            }
        ]
    }


def chunk_transit(data, slug, name):
    """Transit section."""
    transit = data.get("transit", {})
    if not transit or transit.get("stop_count", 0) == 0:
        return None

    text = f"{name} transit. "
    text += f"{transit['stop_count']} transit stops "
    if transit.get("stops_per_1000"):
        text += f"({transit['stops_per_1000']} per 1,000 residents). "

    routes = transit.get("routes", [])
    if routes:
        text += "Key routes: "
        for r in routes:
            text += f"Route {r['route']} ({r['destination']}), "
        text = text.rstrip(", ") + ". "

    return {
        "id": f"{slug}-transit",
        "community": slug,
        "section": "transit",
        "url": f"{PULSE_BASE_URL}/{slug}#transit",
        "text": text,
        "viz": [
            {
                "type": "stat-with-list",
                "component": "TransitSection",
                "data_keys": ["transit.stop_count", "transit.stops_per_1000", "transit.routes"],
                "description": "Stop count metric card plus list of top 5 routes with destinations"
            }
        ]
    }


def chunk_demographics(data, slug, name):
    """Demographics section."""
    demo = data.get("demographics", {})
    if not demo:
        return None

    text = f"{name} demographics (Census 2021). "
    if demo.get("median_age"):
        text += f"Median age: {demo['median_age']}. "
    if demo.get("avg_income"):
        text += f"Average income: {format_currency(demo['avg_income'])}. "
    if demo.get("owner_pct") is not None:
        text += f"Homeowners: {demo['owner_pct']}%, Renters: {demo.get('renter_pct', 'N/A')}%. "
    if demo.get("visible_minority_pct") is not None:
        text += f"Visible minority: {demo['visible_minority_pct']}%. "

    return {
        "id": f"{slug}-demographics",
        "community": slug,
        "section": "demographics",
        "url": f"{PULSE_BASE_URL}/{slug}#demographics",
        "text": text,
        "viz": [
            {
                "type": "stat-grid",
                "component": "DemographicsSection",
                "data_keys": ["demographics.owner_pct", "demographics.renter_pct",
                              "demographics.median_age", "demographics.avg_income",
                              "demographics.visible_minority_pct"],
                "description": "5-column responsive stat grid: Owner %, Renter %, Median Age, Average Income, Visible Minority %"
            }
        ]
    }


def chunk_business(data, slug, name):
    """Business and development section."""
    bd = data.get("business_development", {})
    bc = data.get("business_character", {})
    if not bd and not bc:
        return None

    text = f"{name} business and development. "

    if bc:
        text += f"Business character: {bc.get('character', 'N/A')}. "
        text += f"Total active businesses: {bc.get('total_businesses', 'N/A'):,}. "

    licenses = bd.get("business_licenses", {})
    if licenses:
        text += f"Active business licenses: {licenses.get('active_total', 'N/A'):,} "
        text += f"(city average: {licenses.get('city_avg_active', 'N/A')}). "
        top = licenses.get("top_types", [])
        if top:
            text += "Top types: "
            for t in top:
                text += f"{t['type']} ({t['count']}), "
            text = text.rstrip(", ") + ". "

    permits = bd.get("building_permits", {})
    if permits:
        text += f"Building permits (12 months): {permits.get('total_12mo', 'N/A')} "
        text += f"({format_pct(permits.get('total_yoy_pct', 0))} YoY). "
        if permits.get("units_created_12mo"):
            text += f"Units created: {permits['units_created_12mo']:,}. "
        if permits.get("total_value_12mo"):
            text += f"Total permit value: {format_currency(permits['total_value_12mo'])}. "

    return {
        "id": f"{slug}-business",
        "community": slug,
        "section": "business-development",
        "url": f"{PULSE_BASE_URL}/{slug}#business",
        "text": text,
        "viz": [
            {
                "type": "stat-cards",
                "component": "BusinessDevelopmentSection",
                "data_keys": ["business_development.business_licenses.active_total",
                              "business_development.business_licenses.city_avg_active",
                              "business_development.building_permits.total_12mo",
                              "business_development.building_permits.units_created_12mo",
                              "business_development.building_permits.total_value_12mo",
                              "business_character.character"],
                "description": "Multi-card layout: business character label, license count vs city avg, permits count, units created, total investment value"
            },
            {
                "type": "horizontal-bar",
                "component": "BusinessDevelopmentSection",
                "data_keys": ["business_development.business_licenses.top_types"],
                "description": "Horizontal bar chart of top business license types with counts"
            }
        ]
    }


def chunk_amenities(data, slug, name):
    """Amenities and lifestyle section."""
    amenities = data.get("amenities", {})
    parks = data.get("parks", [])
    recreation = data.get("recreation")
    landmarks = data.get("landmarks", [])

    if not amenities and not parks and not landmarks:
        return None

    text = f"{name} amenities and lifestyle. "

    if amenities:
        grocery = amenities.get("grocery", [])
        if grocery:
            text += f"Grocery stores: {', '.join(grocery[:5])}"
            if len(grocery) > 5:
                text += f" (+{len(grocery)-5} more)"
            text += ". "
        if amenities.get("restaurant_count"):
            text += f"Restaurants: {amenities['restaurant_count']}. "
        if amenities.get("cafe_count"):
            text += f"Cafes: {amenities['cafe_count']}. "
        pharmacy = amenities.get("pharmacy", [])
        if pharmacy:
            text += f"Pharmacies: {len(pharmacy)}. "
        childcare = amenities.get("childcare", [])
        if childcare:
            text += f"Childcare: {len(childcare)} centres. "

    if parks:
        text += f"Parks: {', '.join(p['name'] for p in parks[:3])}. "

    if landmarks:
        text += f"Landmarks: {', '.join(l['name'] for l in landmarks[:5])}. "

    if recreation:
        text += f"Recreation facilities: {', '.join(r['name'] for r in recreation[:3])}. "

    return {
        "id": f"{slug}-amenities",
        "community": slug,
        "section": "amenities",
        "url": f"{PULSE_BASE_URL}/{slug}#amenities",
        "text": text,
        "viz": [
            {
                "type": "named-lists",
                "component": "AmenitiesSection",
                "data_keys": ["amenities.grocery", "amenities.pharmacy", "amenities.childcare",
                              "amenities.restaurant_count", "amenities.cafe_count"],
                "description": "Named lists: grocery stores, pharmacies, childcare centres, plus restaurant and cafe counts"
            },
            {
                "type": "named-lists",
                "component": "CommunityHighlightsSection",
                "data_keys": ["landmarks", "parks", "recreation", "natural_areas"],
                "description": "Named lists: landmarks (by type), parks, recreation facilities, natural areas"
            }
        ]
    }


def chunk_community(filepath):
    """Chunk a single community JSON file into text chunks."""
    with open(filepath) as f:
        data = json.load(f)

    slug = data.get("slug", filepath.stem)
    name = data.get("name", slug.upper())

    chunkers = [
        chunk_hero,
        chunk_safety,
        chunk_housing,
        chunk_311,
        chunk_schools,
        chunk_transit,
        chunk_demographics,
        chunk_business,
        chunk_amenities,
    ]

    chunks = []
    for chunker_fn in chunkers:
        chunk = chunker_fn(data, slug, name)
        if chunk:
            chunks.append(chunk)

    return chunks


def chunk_all(data_dir):
    """Chunk all community JSON files in a directory."""
    data_dir = Path(data_dir)
    all_chunks = []

    for filepath in sorted(data_dir.glob("*.json")):
        if filepath.stem.startswith("_"):
            continue
        chunks = chunk_community(filepath)
        all_chunks.extend(chunks)

    return all_chunks


if __name__ == "__main__":
    import sys

    data_dir = sys.argv[1] if len(sys.argv) > 1 else "data/communities"
    chunks = chunk_all(data_dir)

    print(f"Chunked {len(set(c['community'] for c in chunks))} communities into {len(chunks)} chunks\n")

    for chunk in chunks[:3]:
        print(f"--- {chunk['id']} ({chunk['url']}) ---")
        print(f"Viz: {[v['type'] + ' (' + v['component'] + ')' for v in chunk.get('viz', [])]}")
        print(chunk["text"][:200] + "...")
        print()
