"""
tracer.py
---------
Core Tracing Engine with Exchange/VASP Identification, Risk Flagging, and Parallel Fetching.
Supports full multi-hop traversal while distinctly highlighting matched Exchange VASPs.
"""

import networkx as nx
import time
from typing import Dict, Any, List, Set, Tuple
from collections import deque
from concurrent.futures import ThreadPoolExecutor, as_completed
from adapters import AbstractChainAdapter, detect_adapter
from exchanges import check_address_entity

class CryptoTracer:
    """
    Multi-hop blockchain transaction graph builder with parallel thread fetching.
    """
    
    def __init__(self, adapter: AbstractChainAdapter):
        self.adapter = adapter
        
    def trace_wallet(self, start_address: str, max_depth: int = 3, max_tx_per_node: int = 4, stop_at_exchange: bool = False) -> Tuple[nx.DiGraph, List[Dict[str, Any]], Dict[str, Any]]:
        """
        Build multi-hop transaction graph with exchange matching, parallel fetching, and risk analysis.
        
        Args:
            start_address: Suspect wallet address.
            max_depth: Maximum hops to traverse (default 3-4).
            max_tx_per_node: Branching limit per node.
            stop_at_exchange: If True, prunes traversal upon hitting an exchange. Default False (full graph).
        """
        graph = nx.DiGraph()
        clean_start = start_address.strip()
        if clean_start.startswith("0x"):
            clean_start = clean_start.lower()
            
        risk_flags = []
        
        # Check start node entity
        origin_entity = check_address_entity(clean_start)
        graph.add_node(
            clean_start,
            hop_level=0,
            is_origin=True,
            entity=origin_entity,
            label=origin_entity["name"] if origin_entity else f"Suspect Wallet ({clean_start[:6]}...{clean_start[-4:]})",
            color=origin_entity["color"] if origin_entity else "#F59E0B"
        )
        
        current_level_addresses = [clean_start]
        visited: Set[str] = {clean_start}
        exchanges_reached = []
        
        for depth in range(max_depth):
            if not current_level_addresses:
                break
                
            expandable_addresses = []
            for addr in current_level_addresses:
                ent = check_address_entity(addr)
                if ent and ent["entity_type"] == "EXCHANGE" and addr != clean_start:
                    if ent not in exchanges_reached:
                        exchanges_reached.append(ent)
                    if not stop_at_exchange:
                        expandable_addresses.append(addr)
                else:
                    expandable_addresses.append(addr)
                    
            if not expandable_addresses:
                break
                
            next_level_addresses = []
            
            # Execute parallel HTTP fetching across all addresses at current hop depth level
            with ThreadPoolExecutor(max_workers=min(10, len(expandable_addresses))) as executor:
                future_to_addr = {
                    executor.submit(self.adapter.fetch_outgoing_transactions, addr, max_tx_per_node): addr
                    for addr in expandable_addresses
                }
                
                for future in as_completed(future_to_addr):
                    current_address = future_to_addr[future]
                    try:
                        outgoing_txs = future.result()
                    except Exception as e:
                        print(f"[CryptoTracer] Error fetching for {current_address}: {e}")
                        outgoing_txs = []
                        
                    # Risk Flag 1: Fan-out Pattern Detection
                    if len(outgoing_txs) >= 4:
                        risk_flags.append({
                            "code": "FAN_OUT_SPLIT",
                            "severity": "HIGH",
                            "title": "Fan-Out Fund Splitting Detected",
                            "description": f"Wallet {current_address[:10]}... split funds rapidly into {len(outgoing_txs)} distinct destination wallets.",
                            "node": current_address
                        })
                        
                    last_timestamp = None
                    
                    for tx in outgoing_txs:
                        dest_address = tx["to"]
                        entity_info = check_address_entity(dest_address)
                        
                        node_color = "#3B82F6"
                        node_label = f"Wallet ({dest_address[:6]}...{dest_address[-4:]})"
                        
                        if entity_info:
                            node_color = entity_info["color"]
                            node_label = entity_info["name"]
                            
                            if entity_info["entity_type"] == "EXCHANGE":
                                if entity_info not in exchanges_reached:
                                    exchanges_reached.append(entity_info)
                            elif entity_info["entity_type"] == "MIXER":
                                risk_flags.append({
                                    "code": "MIXER_ROUTING",
                                    "severity": "CRITICAL",
                                    "title": "Mixer / Tumbler Interaction Flag",
                                    "description": f"Funds routed directly into privacy mixer contract ({entity_info['name']}).",
                                    "node": dest_address
                                })
                        
                        if dest_address not in graph:
                            graph.add_node(
                                dest_address,
                                hop_level=depth + 1,
                                is_origin=False,
                                entity=entity_info,
                                label=node_label,
                                color=node_color
                            )
                            
                        graph.add_edge(
                            tx["from"],
                            dest_address,
                            amount=tx["amount"],
                            currency=tx.get("currency", "ETH"),
                            timestamp=tx["timestamp"],
                            tx_hash=tx["tx_hash"]
                        )
                        
                        # Risk Flag 2: Rapid Layering (< 15 mins)
                        if last_timestamp and abs(tx["timestamp"] - last_timestamp) < 900:
                            risk_flags.append({
                                "code": "RAPID_LAYERING",
                                "severity": "MEDIUM",
                                "title": "Rapid Automated Layering",
                                "description": f"Consecutive transfers executed within {abs(tx['timestamp'] - last_timestamp)} seconds.",
                                "node": current_address
                            })
                        last_timestamp = tx["timestamp"]
                        
                        if dest_address not in visited:
                            visited.add(dest_address)
                            next_level_addresses.append(dest_address)
                            
            current_level_addresses = next_level_addresses
            
        risk_score = "LOW"
        if any(f["severity"] == "CRITICAL" for f in risk_flags):
            risk_score = "CRITICAL"
        elif any(f["severity"] == "HIGH" for f in risk_flags):
            risk_score = "HIGH"
        elif len(risk_flags) > 0:
            risk_score = "MEDIUM"
            
        summary = {
            "origin_wallet": clean_start,
            "chain": self.adapter.get_chain_name(),
            "total_nodes": graph.number_of_nodes(),
            "total_edges": graph.number_of_edges(),
            "exchanges_reached": exchanges_reached,
            "risk_score": risk_score,
            "risk_flags_count": len(risk_flags),
            "max_depth": max_depth
        }
        
        return graph, risk_flags, summary
