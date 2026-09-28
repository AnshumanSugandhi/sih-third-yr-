"""
tracer.py
---------
Core Tracing Engine with Exchange/VASP Identification, Risk Flagging, and Parallel Fetching.
Supports full multi-hop traversal while distinctly highlighting matched Exchange VASPs.
Guarantees 100% deterministic graph construction and plain-text trace output.
"""

import networkx as nx
import time
from typing import Dict, Any, List, Set, Tuple
from concurrent.futures import ThreadPoolExecutor
from adapters import AbstractChainAdapter
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
        Deterministic order is strictly preserved at every depth.
        
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
        text_trace_lines = []
        
        # Check start node entity
        origin_entity = check_address_entity(clean_start)
        graph.add_node(
            clean_start,
            hop_level=0,
            is_origin=True,
            entity=origin_entity,
            label=origin_entity["name"] if origin_entity else "Suspect Wallet (Origin)",
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
                
            # Deterministically sort expandable addresses for reproducible thread processing
            sorted_expandable = sorted(expandable_addresses)
            next_level_addresses = []
            
            # Execute parallel HTTP fetching across all addresses at current hop depth level
            with ThreadPoolExecutor(max_workers=min(10, len(sorted_expandable))) as executor:
                futures_map = {
                    addr: executor.submit(self.adapter.fetch_outgoing_transactions, addr, max_tx_per_node)
                    for addr in sorted_expandable
                }
                
                # Iterate in strict deterministic order of sorted input addresses
                for current_address in sorted_expandable:
                    future = futures_map[current_address]
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
                        # Strict label rule: If entity is in dataset, use real name. Otherwise, label "Unknown wallet"
                        node_label = entity_info["name"] if entity_info else "Unknown wallet"
                        
                        if entity_info:
                            node_color = entity_info["color"]
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
                            elif entity_info["entity_type"] == "BRIDGE":
                                risk_flags.append({
                                    "code": "CROSS_CHAIN_SWAP",
                                    "severity": "HIGH",
                                    "title": "AI: Cross-Chain Fund Movement Detected",
                                    "description": f"Funds routed into {entity_info['name']}. High probability of cross-chain chainhopping or DEX swapping.",
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
                        
                        # Generate plain-text trace output line
                        curr_symbol = tx.get("currency", "BTC")
                        trace_line = f"Hop {depth + 1}: [{tx['from']}] sent {tx['amount']} {curr_symbol} to [{dest_address}]"
                        text_trace_lines.append(trace_line)
                        
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
            "max_depth": max_depth,
            "text_trace": text_trace_lines,
            "text_trace_plain": "\n".join(text_trace_lines)
        }
        
        return graph, risk_flags, summary
