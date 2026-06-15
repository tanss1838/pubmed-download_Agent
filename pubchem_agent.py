"""
PubChem AI Agent — Thermoset Compound Downloader
-------------------------------------------------
Uses Claude AI as an agent brain to:
  1. Decide the best PubChem search strategy for the keyword
  2. Query PubChem API automatically
  3. Fetch full compound data sheets
  4. Save everything to a local folder as CSV + JSON

Run:
    pip install requests anthropic
    python pubchem_agent.py
"""

import os
import sys
import json
import time
import csv
from datetime import datetime
from pathlib import Path

try:
    import requests
except ImportError:
    print("Missing: pip install requests")
    sys.exit(1)

try:
    import anthropic
except ImportError:
    print("Missing: pip install anthropic")
    sys.exit(1)


# ─────────────────────────────────────────────
#  CONFIG
# ─────────────────────────────────────────────

KEYWORD     = "thermoset"
COUNT       = 100
OUTPUT_DIR  = Path("pubchem_thermoset_data")
PUBCHEM_BASE = "https://pubchem.ncbi.nlm.nih.gov/rest/pug"
DELAY       = 0.3   # seconds between PubChem requests


# ─────────────────────────────────────────────
#  PUBCHEM FUNCTIONS (tools the agent can call)
# ─────────────────────────────────────────────

def search_pubchem_by_name(keyword: str, count: int) -> dict:
    """Search PubChem compounds by name keyword, return CIDs."""
    url = f"{PUBCHEM_BASE}/compound/name/{requests.utils.quote(keyword)}/cids/JSON"
    try:
        time.sleep(DELAY)
        r = requests.get(url, timeout=15)
        if r.status_code == 404:
            return {"success": False, "cids": [], "message": f"No compounds found for '{keyword}'"}
        r.raise_for_status()
        cids = r.json().get("IdentifierList", {}).get("CID", [])
        cids = cids[:count]
        return {"success": True, "cids": [str(c) for c in cids], "count": len(cids)}
    except Exception as e:
        return {"success": False, "cids": [], "message": str(e)}


def search_pubchem_by_keyword(keyword: str, count: int) -> dict:
    """Full-text search PubChem for compounds matching keyword."""
    url = f"https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/fastsimilarity_2d/cids/JSON"
    # Use the broader text search endpoint
    url2 = f"https://pubchem.ncbi.nlm.nih.gov/rest/pug_view/search/compound/json/?query={requests.utils.quote(keyword)}&limit={count}"
    try:
        time.sleep(DELAY)
        r = requests.get(url2, timeout=20)
        if r.status_code == 200:
            data = r.json()
            cids = data.get("IdentifierList", {}).get("CID", [])
            return {"success": True, "cids": [str(c) for c in cids[:count]], "count": len(cids[:count])}
        return {"success": False, "cids": [], "message": f"HTTP {r.status_code}"}
    except Exception as e:
        return {"success": False, "cids": [], "message": str(e)}


def fetch_compound_properties(cids: list) -> dict:
    """Fetch detailed properties for a batch of CIDs."""
    if not cids:
        return {"success": False, "compounds": [], "message": "No CIDs provided"}

    properties = (
        "IUPACName,MolecularFormula,MolecularWeight,"
        "CanonicalSMILES,InChI,InChIKey,"
        "XLogP,TPSA,HBondDonorCount,HBondAcceptorCount,"
        "RotatableBondCount,HeavyAtomCount,Complexity,"
        "Charge,IsotopeAtomCount,CovalentUnitCount"
    )

    # PubChem accepts max ~200 CIDs per request; chunk if needed
    batch_size = 100
    all_compounds = []

    for i in range(0, len(cids), batch_size):
        batch = cids[i:i+batch_size]
        url = f"{PUBCHEM_BASE}/compound/cid/{','.join(batch)}/property/{properties}/JSON"
        try:
            time.sleep(DELAY)
            r = requests.get(url, timeout=30)
            r.raise_for_status()
            props = r.json().get("PropertyTable", {}).get("Properties", [])
            all_compounds.extend(props)
        except Exception as e:
            print(f"  [Warning] Batch {i//batch_size + 1} failed: {e}")

    return {"success": True, "compounds": all_compounds, "count": len(all_compounds)}


def fetch_compound_synonyms(cids: list) -> dict:
    """Fetch common names/synonyms for compounds."""
    synonyms_map = {}
    for cid in cids[:20]:  # limit to first 20 to avoid too many requests
        url = f"{PUBCHEM_BASE}/compound/cid/{cid}/synonyms/JSON"
        try:
            time.sleep(DELAY)
            r = requests.get(url, timeout=10)
            if r.status_code == 200:
                syns = r.json().get("InformationList", {}).get("Information", [{}])[0].get("Synonym", [])
                synonyms_map[cid] = syns[:5]  # top 5 synonyms
        except:
            synonyms_map[cid] = []
    return {"success": True, "synonyms": synonyms_map}


# ─────────────────────────────────────────────
#  SAVE FUNCTIONS
# ─────────────────────────────────────────────

def save_to_csv(compounds: list, keyword: str, output_dir: Path):
    if not compounds:
        return None
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = output_dir / f"pubchem_{keyword}_{timestamp}.csv"
    with open(filename, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=compounds[0].keys())
        writer.writeheader()
        writer.writerows(compounds)
    return str(filename)


def save_to_json(compounds: list, keyword: str, output_dir: Path):
    if not compounds:
        return None
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = output_dir / f"pubchem_{keyword}_{timestamp}.json"
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(compounds, f, indent=2)
    return str(filename)


# ─────────────────────────────────────────────
#  AGENT TOOL DISPATCHER
# ─────────────────────────────────────────────

TOOLS = [
    {
        "name": "search_pubchem_by_name",
        "description": "Search PubChem for compounds by a name or keyword. Returns a list of CIDs (Compound IDs). Use this first to find relevant compounds.",
        "input_schema": {
            "type": "object",
            "properties": {
                "keyword": {"type": "string", "description": "The search keyword or compound name"},
                "count":   {"type": "integer", "description": "Max number of CIDs to return"}
            },
            "required": ["keyword", "count"]
        }
    },
    {
        "name": "fetch_compound_properties",
        "description": "Fetch detailed chemical properties (molecular formula, weight, SMILES, InChI, XLogP, TPSA, etc.) for a list of CIDs. Call this after getting CIDs.",
        "input_schema": {
            "type": "object",
            "properties": {
                "cids": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of PubChem CIDs to fetch properties for"
                }
            },
            "required": ["cids"]
        }
    },
    {
        "name": "fetch_compound_synonyms",
        "description": "Fetch common names and synonyms for a list of CIDs. Useful to enrich data with trade names.",
        "input_schema": {
            "type": "object",
            "properties": {
                "cids": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of CIDs to get synonyms for"
                }
            },
            "required": ["cids"]
        }
    }
]


def dispatch_tool(tool_name: str, tool_input: dict) -> str:
    """Execute a tool call and return result as string."""
    print(f"  → Tool: {tool_name}({json.dumps(tool_input, separators=(',',':'))[:80]}...)")
    if tool_name == "search_pubchem_by_name":
        result = search_pubchem_by_name(tool_input["keyword"], tool_input["count"])
    elif tool_name == "fetch_compound_properties":
        result = fetch_compound_properties(tool_input["cids"])
    elif tool_name == "fetch_compound_synonyms":
        result = fetch_compound_synonyms(tool_input["cids"])
    else:
        result = {"error": f"Unknown tool: {tool_name}"}
    return json.dumps(result)


# ─────────────────────────────────────────────
#  AGENT LOOP
# ─────────────────────────────────────────────

def run_agent(keyword: str, count: int):
    client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from env automatically

    system_prompt = """You are a PubChem research agent. Your job is to:
1. Search PubChem for compounds related to a keyword
2. Fetch detailed property data sheets for those compounds
3. Optionally enrich with synonyms
4. Return a final summary when done

Always use the tools provided. Search first, then fetch properties for ALL the CIDs you find.
Be systematic and thorough. Do not stop until you have fetched properties for all found compounds."""

    user_message = f"""Download compound data sheets from PubChem for the keyword: "{keyword}"
Target count: {count} compounds.

Steps:
1. Search PubChem for compounds related to "{keyword}"
2. Fetch full property data for all found CIDs
3. Also fetch synonyms for the top compounds
4. Summarize what you found at the end."""

    messages = [{"role": "user", "content": user_message}]
    all_compounds = []
    all_cids = []

    print(f"\n[Agent] Starting PubChem research for '{keyword}' (target: {count} compounds)")
    print("=" * 60)

    # Agentic loop
    while True:
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4096,
            system=system_prompt,
            tools=TOOLS,
            messages=messages
        )

        # Collect any text output
        for block in response.content:
            if block.type == "text" and block.text.strip():
                print(f"\n[Agent] {block.text.strip()}")

        # If no tool calls, agent is done
        if response.stop_reason == "end_turn":
            break

        # Process tool calls
        tool_results = []
        for block in response.content:
            if block.type == "tool_use":
                result_str = dispatch_tool(block.name, block.input)
                result_data = json.loads(result_str)

                # Capture CIDs and compounds as they come in
                if block.name == "search_pubchem_by_name" and result_data.get("success"):
                    all_cids = result_data.get("cids", [])
                    print(f"  ✓ Found {len(all_cids)} CIDs")

                if block.name == "fetch_compound_properties" and result_data.get("success"):
                    fetched = result_data.get("compounds", [])
                    all_compounds.extend(fetched)
                    print(f"  ✓ Fetched {len(fetched)} compound records (total: {len(all_compounds)})")

                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": result_str
                })

        # Add assistant response + tool results to message history
        messages.append({"role": "assistant", "content": response.content})
        messages.append({"role": "user",      "content": tool_results})

    return all_compounds


# ─────────────────────────────────────────────
#  MAIN
# ─────────────────────────────────────────────

def main():
    print("\n" + "=" * 60)
    print("  PubChem AI Agent — Compound Data Downloader")
    print("=" * 60)
    print(f"  Keyword : {KEYWORD}")
    print(f"  Count   : {COUNT}")
    print(f"  Output  : {OUTPUT_DIR}/")
    print("=" * 60)

    # Check API key
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("\n[Error] ANTHROPIC_API_KEY environment variable not set.")
        print("Set it with:")
        print("  Windows : set ANTHROPIC_API_KEY=your_key_here")
        print("  Mac/Linux: export ANTHROPIC_API_KEY=your_key_here")
        sys.exit(1)

    # Run agent
    compounds = run_agent(KEYWORD, COUNT)

    if not compounds:
        print("\n[Warning] No compound data retrieved.")
        return

    # Add PubChem link to each record
    for c in compounds:
        cid = str(c.get("CID", ""))
        c["PubChem_Link"] = f"https://pubchem.ncbi.nlm.nih.gov/compound/{cid}"

    # Save outputs
    print("\n[Saving] Writing data files...")
    csv_path  = save_to_csv(compounds,  KEYWORD, OUTPUT_DIR)
    json_path = save_to_json(compounds, KEYWORD, OUTPUT_DIR)

    print(f"\n{'=' * 60}")
    print(f"  ✅ Done! {len(compounds)} compounds downloaded.")
    print(f"  📄 CSV  → {csv_path}")
    print(f"  📦 JSON → {json_path}")
    print(f"{'=' * 60}\n")


if __name__ == "__main__":
    main()