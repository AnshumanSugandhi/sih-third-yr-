"""
main.py
-------
Command-line test runner for Feature 1: Core Tracing Engine.
Supports both Ethereum (Etherscan V2) and Bitcoin (Blockstream Explorer) addresses.
"""

import sys
import json

# Ensure stdout handles UTF-8 on Windows
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

from adapters import detect_adapter
from tracer import CryptoTracer

DEFAULT_TEST_ADDRESS = "149w62rY42aZBox8fGcmqNsXUzSStKeq8C"

def print_graph_tree(graph, root_address: str):
    """Utility to print a readable tree structure of the traced graph."""
    clean_root = root_address.strip()
    if clean_root.startswith("0x"):
        clean_root = clean_root.lower()
        
    print("\n" + "="*75)
    print("                 TRANSACTION GRAPH TRACE TREE")
    print("="*75)
    print(f"Origin Wallet Address        : {clean_root}")
    print(f"Total Unique Wallets (Nodes) : {graph.number_of_nodes()}")
    print(f"Total Transfers (Edges)      : {graph.number_of_edges()}")
    print("-" * 75)
    
    def _dfs_print(node: str, depth: int, prefix: str = ""):
        successors = list(graph.successors(node))
        for idx, child in enumerate(successors):
            edge_data = graph.get_edge_data(node, child)
            amount = edge_data.get("amount", 0.0)
            currency = edge_data.get("currency", "ETH")
            is_last = (idx == len(successors) - 1)
            connector = "└── " if is_last else "├── "
            
            node_attrs = graph.nodes[child]
            label = node_attrs.get("label", child[:12])
            
            print(f"{prefix}{connector}[Hop {depth}] {child} ({label}) | Sent: {amount} {currency}")
            
            new_prefix = prefix + ("    " if is_last else "│   ")
            _dfs_print(child, depth + 1, new_prefix)
            
    _dfs_print(clean_root, 1)
    print("="*75 + "\n")


def run_trace(address: str, max_depth: int = 3, max_tx_per_node: int = 4):
    """
    Executes tracing logic end-to-end for Ethereum or Bitcoin wallet addresses.
    """
    print("=" * 75)
    print("      SIH 2026 - REAL-TIME CRYPTO FRAUD WALLET TRACER (SAMSAM BTC TEST)")
    print("=" * 75)
    
    # 1. Auto-detect adapter (Ethereum vs Bitcoin)
    adapter = detect_adapter(address)
    print(f"[Entry Routing] Detected Blockchain: {adapter.get_chain_name()}")
    
    # 2. Instantiate Core Tracer
    tracer = CryptoTracer(adapter=adapter)
    
    # 3. Build Multi-hop Transaction Graph
    graph, risk_flags, summary = tracer.trace_wallet(
        start_address=address,
        max_depth=max_depth,
        max_tx_per_node=max_tx_per_node
    )
    
    # 4. Display Tree Output
    print_graph_tree(graph=graph, root_address=address)
    
    # 5. Display Summary & Risk Flags
    print(f"Chain           : {summary['chain']}")
    print(f"Risk Score      : {summary['risk_score']}")
    print(f"Risk Flags Count: {summary['risk_flags_count']}")
    
    if summary['exchanges_reached']:
        print("\nTarget Exchanges Reached (VASPs):")
        for ex in summary['exchanges_reached']:
            print(f"  - {ex['name']} ({ex['category']}, {ex['country']})")
    else:
        print("\nTarget Exchanges Reached: None identified within configured hops.")
        
    print("\n✅ Core Tracing Engine test execution complete!\n")
    return graph, risk_flags, summary


if __name__ == "__main__":
    target_address = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_TEST_ADDRESS
    max_hops = int(sys.argv[2]) if len(sys.argv) > 2 else 3
    run_trace(target_address, max_depth=max_hops)
