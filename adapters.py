"""
adapters.py
-----------
Modular Chain Adapter Interface for Ethereum (Etherscan V2) and Bitcoin (Blockstream API).
Includes strict regex format validation for Ethereum and Bitcoin wallet addresses.
"""

from abc import ABC, abstractmethod
import requests
import time
import re
from typing import List, Dict, Any, Optional

# Strict Address Validation Regex
ETH_REGEX = re.compile(r"^0x[a-fA-F0-9]{40}$")
BTC_REGEX = re.compile(r"^(1[a-km-zA-HJ-NP-Z1-9]{25,34}|3[a-km-zA-HJ-NP-Z1-9]{25,34}|bc1[ac-hj-np-z0-9]{11,87})$", re.IGNORECASE)


class AbstractChainAdapter(ABC):
    """
    Abstract Base Class defining the contract for all blockchain adapters.
    """
    
    @abstractmethod
    def fetch_outgoing_transactions(self, address: str, limit: int = 10) -> List[Dict[str, Any]]:
        pass

    @abstractmethod
    def get_chain_name(self) -> str:
        pass


class EthereumAdapter(AbstractChainAdapter):
    """
    Ethereum Blockchain Adapter using Etherscan API V2.
    """
    
    def __init__(self, api_key: str = "K2KZB43NXYW39622M7INMJC5ZUVYIJG2ES"):
        self.api_key = api_key
        self.base_url = "https://api.etherscan.io/v2/api"
        
    def get_chain_name(self) -> str:
        return "Ethereum (ETH)"
        
    def fetch_outgoing_transactions(self, address: str, limit: int = 10) -> List[Dict[str, Any]]:
        clean_address = address.strip().lower()
        params = {
            "chainid": "1",
            "module": "account",
            "action": "txlist",
            "address": clean_address,
            "startblock": 0,
            "endblock": 99999999,
            "page": 1,
            "offset": 100,
            "sort": "asc",
            "apikey": self.api_key
        }
        
        try:
            time.sleep(0.25)
            response = requests.get(self.base_url, params=params, timeout=10)
            data = response.json()
            
            if data.get("status") != "1" or not isinstance(data.get("result"), list):
                return []
            
            outgoing_txs = []
            seen_destinations = set()
            
            for tx in data["result"]:
                if tx.get("isError") != "0":
                    continue
                
                tx_from = (tx.get("from") or "").lower()
                tx_to = (tx.get("to") or "").lower()
                
                if tx_from == clean_address and tx_to and tx_to != clean_address:
                    wei_val = float(tx.get("value", 0))
                    eth_val = wei_val / (10 ** 18)
                    
                    if tx_to not in seen_destinations:
                        seen_destinations.add(tx_to)
                        outgoing_txs.append({
                            "from": clean_address,
                            "to": tx_to,
                            "amount": round(eth_val, 6),
                            "currency": "ETH",
                            "timestamp": int(tx.get("timeStamp", 0)),
                            "tx_hash": tx.get("hash", "")
                        })
                    
                    if len(outgoing_txs) >= limit:
                        break
                        
            return outgoing_txs
            
        except Exception as e:
            print(f"[EthereumAdapter] Error fetching txs for {address}: {e}")
            return []


class BitcoinAdapter(AbstractChainAdapter):
    """
    Bitcoin Blockchain Adapter using Blockstream API (Free, no API key required).
    """
    
    def __init__(self):
        self.base_url = "https://blockstream.info/api"
        
    def get_chain_name(self) -> str:
        return "Bitcoin (BTC)"
        
    def fetch_outgoing_transactions(self, address: str, limit: int = 10) -> List[Dict[str, Any]]:
        clean_address = address.strip()
        url = f"{self.base_url}/address/{clean_address}/txs"
        
        try:
            time.sleep(0.2)
            response = requests.get(url, timeout=10)
            if response.status_code != 200:
                return []
                
            tx_data = response.json()
            outgoing_txs = []
            seen_destinations = set()
            
            for tx in tx_data:
                is_sender = any(
                    vin.get("prevout", {}).get("scriptpubkey_address") == clean_address
                    for vin in tx.get("vin", [])
                )
                
                if not is_sender:
                    continue
                    
                timestamp = tx.get("status", {}).get("block_time", int(time.time()))
                tx_id = tx.get("txid", "")
                
                for vout in tx.get("vout", []):
                    recip_addr = vout.get("scriptpubkey_address")
                    if recip_addr and recip_addr != clean_address and recip_addr not in seen_destinations:
                        sats = vout.get("value", 0)
                        btc_val = sats / (10 ** 8)
                        
                        seen_destinations.add(recip_addr)
                        outgoing_txs.append({
                            "from": clean_address,
                            "to": recip_addr,
                            "amount": round(btc_val, 6),
                            "currency": "BTC",
                            "timestamp": timestamp,
                            "tx_hash": tx_id
                        })
                        
                        if len(outgoing_txs) >= limit:
                            break
                            
                if len(outgoing_txs) >= limit:
                    break
                    
            return outgoing_txs
            
        except Exception as e:
            print(f"[BitcoinAdapter] Error fetching BTC txs for {address}: {e}")
            return []


def detect_chain_type(address: str) -> str:
    """
    Strictly detect blockchain type from address format rules:
    - Ethereum: Starts with '0x' followed by 40 hex chars (42 total length).
    - Bitcoin: Starts with '1', '3', or 'bc1' matching standard BTC base58/bech32 length and character set.
    - Invalid: Returns 'UNKNOWN'
    """
    clean_addr = address.strip()
    if ETH_REGEX.match(clean_addr):
        return "ETH"
    elif BTC_REGEX.match(clean_addr):
        return "BTC"
    else:
        return "UNKNOWN"


def detect_adapter(address: str, eth_api_key: str = "K2KZB43NXYW39622M7INMJC5ZUVYIJG2ES") -> AbstractChainAdapter:
    """
    Strictly routes address to EthereumAdapter or BitcoinAdapter based on chain format detection.
    Raises ValueError for unrecognized address formats.
    """
    chain_type = detect_chain_type(address)
    if chain_type == "ETH":
        return EthereumAdapter(api_key=eth_api_key)
    elif chain_type == "BTC":
        return BitcoinAdapter()
    else:
        raise ValueError(
            "Unrecognized or invalid wallet address format. Please enter a valid Ethereum address "
            "(starts with '0x', 42 characters) or Bitcoin address (starts with '1', '3', or 'bc1')."
        )
