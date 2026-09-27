"""
app.py
------
Flask Web Application backend for the Real-Time Crypto Fraud Wallet Tracer (SIH 26183).
Supports full 4-hop depth traversal, distinct VASP exchange node highlighting, and hover tooltips.
"""

from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
import os
import json
import time
from adapters import detect_adapter, detect_chain_type, EthereumAdapter, BitcoinAdapter
from tracer import CryptoTracer
from exchanges import check_address_entity, KNOWN_EXCHANGES

app = Flask(__name__, template_folder="templates")
CORS(app)

TRACE_CACHE = {}

SAMPLE_CASES = {
    "eth_vitalik": {
        "title": "Ethereum Multi-Hop Trace (Vitalik Public Wallet)",
        "address": "0xd8da6bf26964af9d7eed9e03e53415d37aa96045",
        "chain": "Ethereum",
        "depth": 3
    },
    "eth_wazirx_scam": {
        "title": "High Risk Exchange Cash-Out Trace (WazirX / Binance Target)",
        "address": "0x28c6c06298d514db089934071355e5743bf21d60",
        "chain": "Ethereum",
        "depth": 3
    },
    "btc_samsam": {
        "title": "Bitcoin SamSam Ransomware OFAC Case",
        "address": "149w62rY42aZBox8fGcmqNsXUzSStKeq8C",
        "chain": "Bitcoin",
        "depth": 3
    }
}


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/trace", methods=["POST", "GET"])
def api_trace():
    if request.method == "POST":
        data = request.get_json(silent=True) or {}
        address = data.get("address", "").strip()
        max_depth = int(data.get("max_depth", 3))
        stop_at_ex = bool(data.get("stop_at_exchange", False))
        api_key = data.get("api_key", "").strip() or "K2KZB43NXYW39622M7INMJC5ZUVYIJG2ES"
    else:
        address = request.args.get("address", "").strip()
        max_depth = int(request.args.get("max_depth", 3))
        stop_at_ex = bool(request.args.get("stop_at_exchange", False))
        api_key = request.args.get("api_key", "").strip() or "K2KZB43NXYW39622M7INMJC5ZUVYIJG2ES"
        
    if not address:
        return jsonify({
            "status": "error",
            "error": "Please enter a victim-reported wallet address."
        }), 400

    cache_key = f"{address.lower()}_{max_depth}_{stop_at_ex}"
    if cache_key in TRACE_CACHE:
        return jsonify(TRACE_CACHE[cache_key])

    try:
        adapter = detect_adapter(address, eth_api_key=api_key)
    except ValueError as val_err:
        return jsonify({
            "status": "error",
            "error": str(val_err)
        }), 400
    except Exception as err:
        return jsonify({
            "status": "error",
            "error": f"Address format routing failed: {str(err)}"
        }), 400
        
    tracer = CryptoTracer(adapter=adapter)
    
    # Execute multi-hop graph trace up to configured depth
    graph, risk_flags, summary = tracer.trace_wallet(
        start_address=address,
        max_depth=max_depth,
        max_tx_per_node=4,
        stop_at_exchange=stop_at_ex
    )
    
    hop_groups = {}
    for node, attrs in graph.nodes(data=True):
        h = attrs.get("hop_level", 0)
        hop_groups.setdefault(h, []).append(node)

    nodes_data = []
    for node, attrs in graph.nodes(data=True):
        entity = attrs.get("entity")
        is_origin = attrs.get("is_origin", False)
        hop_lvl = attrs.get("hop_level", 0)
        
        same_hop_nodes = hop_groups.get(hop_lvl, [node])
        node_index = same_hop_nodes.index(node)
        total_in_hop = len(same_hop_nodes)
        
        x_coord = (hop_lvl * 260) - 300
        y_offset = (node_index - (total_in_hop - 1) / 2.0) * 110
        y_coord = y_offset

        node_type = "UNRESOLVED_BURNER"
        group = "burner"
        shape = "dot"
        size = 22
        hover_title = f"<b>UNRESOLVED BURNER WALLET</b><br>Address: <code>{node}</code><br>Hop Level: {hop_lvl}<br>Status: Anonymous / Untraced"
        
        if is_origin:
            node_type = "SUSPECT_ORIGIN"
            group = "origin"
            shape = "diamond"
            size = 34
            hover_title = f"<b>ORIGIN SUSPECT WALLET</b><br>Address: <code>{node}</code><br>Status: Primary Victim Intake Address"
        elif entity:
            if entity["entity_type"] == "EXCHANGE":
                node_type = "REACHED_EXCHANGE"
                group = "exchange"
                shape = "star"
                size = 38
                hover_title = f"<b>REACHED CUSTODIAL EXCHANGE (VASP)</b><br>Exchange: <b>{entity['name']}</b><br>Category: {entity['category']}<br>Jurisdiction: {entity['country']}<br>KYC Status: Required<br>⚡ <i>Action: Issue SAHYOG Freeze Notice</i>"
            elif entity["entity_type"] == "MIXER":
                node_type = "KNOWN_MIXER"
                group = "mixer"
                shape = "triangle"
                size = 32
                hover_title = f"<b>SANCTIONED PRIVACY MIXER</b><br>Name: <b>{entity['name']}</b><br>Category: {entity['category']}<br>Status: Obfuscation Contract Flagged"
                
        color_hex = attrs.get("color", "#3B82F6")
        if entity and entity["entity_type"] == "EXCHANGE":
            color_hex = "#10B981"  # Glowing Emerald Green for Exchanges
            
        node_color_obj = {
            "background": color_hex,
            "border": "#FFFFFF" if is_origin else color_hex,
            "highlight": {
                "background": "#34D399" if (entity and entity["entity_type"] == "EXCHANGE") else "#60A5FA",
                "border": "#FFFFFF"
            }
        }
        
        nodes_data.append({
            "id": node,
            "label": attrs.get("label", node[:8]),
            "title": hover_title,
            "color": node_color_obj,
            "size": size,
            "shape": shape,
            "group": group,
            "hop": hop_lvl,
            "x": x_coord,
            "y": y_coord,
            "entity": entity,
            "is_origin": is_origin
        })
        
    edges_data = []
    for u, v, attrs in graph.edges(data=True):
        edges_data.append({
            "from": u,
            "to": v,
            "label": f"{attrs.get('amount', 0)} {attrs.get('currency', 'ETH')}",
            "title": f"Tx Hash: <code>{attrs.get('tx_hash', 'N/A')}</code><br>Amount: {attrs.get('amount', 0)} {attrs.get('currency', 'ETH')}",
            "amount": attrs.get("amount", 0),
            "currency": attrs.get("currency", "ETH"),
            "tx_hash": attrs.get("tx_hash", "")
        })
        
    result_payload = {
        "status": "success",
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()),
        "summary": summary,
        "nodes": nodes_data,
        "edges": edges_data,
        "risk_flags": risk_flags
    }
    
    TRACE_CACHE[cache_key] = result_payload
    return jsonify(result_payload)


@app.route("/api/v1/ncrp/ingest", methods=["POST"])
def ncrp_ingest_complaint():
    data = request.get_json(silent=True) or {}
    complaint_id = data.get("complaint_id", f"NCRP-{int(time.time())}")
    suspect_address = data.get("suspect_address", "").strip()
    max_hops = int(data.get("max_hops", 3))

    if not suspect_address:
        return jsonify({
            "status": "FAILED",
            "complaint_id": complaint_id,
            "error": "Missing suspect_address field in NCRP payload."
        }), 400

    try:
        adapter = detect_adapter(suspect_address)
    except ValueError as val_err:
        return jsonify({
            "status": "FAILED",
            "complaint_id": complaint_id,
            "error": str(val_err)
        }), 400

    tracer = CryptoTracer(adapter=adapter)
    graph, risk_flags, summary = tracer.trace_wallet(
        start_address=suspect_address,
        max_depth=max_hops,
        max_tx_per_node=4,
        stop_at_exchange=False
    )

    exchanges = summary.get("exchanges_reached", [])
    action_required = len(exchanges) > 0

    return jsonify({
        "status": "PROCESSED",
        "ncrp_complaint_id": complaint_id,
        "ingest_timestamp": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()),
        "suspect_address": suspect_address,
        "chain_detected": summary.get("chain"),
        "risk_score": summary.get("risk_score"),
        "target_vasps_identified": [e["name"] for e in exchanges],
        "sahyog_freeze_alert_triggered": action_required,
        "sahyog_payload": {
            "notice_type": "URGENT_CRYPTO_FREEZE_NOTICE",
            "issuing_authority": "Ministry of Home Affairs - I4C / CIS Division",
            "ncrp_reference": complaint_id,
            "target_exchanges": exchanges,
            "evidence_summary": f"Automated graph analytics identified {len(exchanges)} destination exchange account(s) within {max_hops} hops."
        }
    })


@app.route("/api/sample_cases")
def sample_cases():
    return jsonify(SAMPLE_CASES)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"\n[>>] Starting Crypto Fraud Wallet Tracer Dashboard on http://127.0.0.1:{port}")
    app.run(host="0.0.0.0", port=port, debug=True)
