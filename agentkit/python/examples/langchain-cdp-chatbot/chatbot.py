import json
import os
import sys
import time
from decimal import Decimal
from typing import Any, Optional

from coinbase_agentkit import (
    AgentKit,
    AgentKitConfig,
    CdpWalletProvider,
    CdpWalletProviderConfig,
    allora_action_provider,
    cdp_api_action_provider,
    cdp_wallet_action_provider,
    erc20_action_provider,
    pyth_action_provider,
    wallet_action_provider,
    weth_action_provider,
)
from coinbase_agentkit_langchain import get_langchain_tools
from dotenv import load_dotenv
from langchain_core.messages import HumanMessage
from langchain_core.tools import Tool
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import MemorySaver
from langgraph.prebuilt import create_react_agent
from web3 import Web3
from web3.types import HexStr

# Configure a file to persist the agent's CDP API Wallet Data.
wallet_data_file = "wallet_data.txt"

load_dotenv()

################################################################################
#                                CONTRACT DETAILS                               #
################################################################################

SMART_CONTRACT_ADDRESS = "0xa633656593bB24252A55A468146fe9536eA899cB"

SMART_CONTRACT_ABI = [
    {
        "inputs": [],
        "stateMutability": "nonpayable",
        "type": "constructor"
    },
    {
        "inputs": [],
        "name": "deposit",
        "outputs": [],
        "stateMutability": "payable",
        "type": "function"
    },
    {
        "inputs": [
            {"internalType": "address", "name": "tokenAddress", "type": "address"},
            {"internalType": "uint256", "name": "amount", "type": "uint256"}
        ],
        "name": "depositERC20",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function"
    },
    {
        "inputs": [],
        "name": "destroyContract",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function"
    },
    {
        "inputs": [],
        "name": "getBalance",
        "outputs": [
            {"internalType": "uint256", "name": "", "type": "uint256"}
        ],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [
            {"internalType": "address", "name": "token", "type": "address"}
        ],
        "name": "getERC20Balance",
        "outputs": [
            {"internalType": "uint256", "name": "", "type": "uint256"}
        ],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [],
        "name": "getCounter",
        "outputs": [
            {"internalType": "uint256", "name": "", "type": "uint256"}
        ],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [],
        "name": "incrementCounter",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function"
    },
    {
        "inputs": [
            {"internalType": "address", "name": "to", "type": "address"},
            {"internalType": "uint256", "name": "amount", "type": "uint256"}
        ],
        "name": "withdraw",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function"
    },
    {
        "inputs": [
            {"internalType": "address", "name": "token", "type": "address"},
            {"internalType": "address", "name": "to", "type": "address"},
            {"internalType": "uint256", "name": "amount", "type": "uint256"}
        ],
        "name": "withdrawERC20",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function"
    }
]


################################################################################
#                                HELPER METHODS                                #
################################################################################

def invoke_contract_function(
    wallet_provider: CdpWalletProvider,
    function_name: str,
    args: Optional[list] = None,
    value: Decimal = Decimal(0)
):
    """Invoke a function on the custom smart contract, optionally payable."""
    try:
        web3 = Web3()
        contract = web3.eth.contract(
            address=SMART_CONTRACT_ADDRESS, 
            abi=SMART_CONTRACT_ABI
        )
        if args is None:
            args = []
        data = contract.encode_abi(function_name, args=args)

        tx_params = {
            "to": HexStr(SMART_CONTRACT_ADDRESS),
            "data": HexStr(data),
        }
        # If function is payable, add ETH value in Wei
        if value > Decimal(0):
            tx_params["value"] = int(value * Decimal(10**18))

        tx_hash = wallet_provider.send_transaction(tx_params)
        wallet_provider.wait_for_transaction_receipt(tx_hash)

        return f"Successfully called {function_name}. Transaction hash: {tx_hash}"
    except Exception as e:
        return f"Error calling {function_name}: {str(e)}"


def read_contract_function(
    wallet_provider: CdpWalletProvider, 
    function_name: str, 
    args: Optional[list] = None
):
    """Read data from the smart contract (no transaction)."""
    try:
        if args is None:
            args = []
        result = wallet_provider.read_contract(
            contract_address=SMART_CONTRACT_ADDRESS,
            abi=SMART_CONTRACT_ABI,
            function_name=function_name,
            args=args
        )
        return result
    except Exception as e:
        return f"Error reading from contract: {str(e)}"


################################################################################
#                           WRAPPERS FOR CONTRACT OPS                           #
################################################################################

def deposit_to_contract(wallet_provider: CdpWalletProvider, value_in_eth: float):
    """Payable deposit of ETH to the contract."""
    return invoke_contract_function(
        wallet_provider, 
        "deposit", 
        value=Decimal(str(value_in_eth))
    )

def deposit_erc20_to_contract(
    wallet_provider: CdpWalletProvider, 
    token_address: str, 
    amount: int
):
    """Deposit ERC20 tokens (amount is raw integer)."""
    return invoke_contract_function(
        wallet_provider,
        "depositERC20",
        args=[token_address, amount]
    )

def increment_counter(wallet_provider: CdpWalletProvider):
    """Increment the counter in the contract."""
    return invoke_contract_function(wallet_provider, "incrementCounter")

def get_contract_balance(wallet_provider: CdpWalletProvider):
    """Retrieve the ETH balance (in Wei) of the contract."""
    return read_contract_function(wallet_provider, "getBalance")

def get_contract_counter(wallet_provider: CdpWalletProvider):
    """Retrieve the contract's current counter value."""
    return read_contract_function(wallet_provider, "getCounter")

def get_contract_erc20_balance(wallet_provider: CdpWalletProvider, token_address: str):
    """Retrieve the ERC20 token balance of the contract."""
    return read_contract_function(wallet_provider, "getERC20Balance", args=[token_address])

def withdraw_from_contract(
    wallet_provider: CdpWalletProvider, 
    to_address: str, 
    amount_in_wei: int
):
    """Withdraw native ETH from the contract to a 'to_address'."""
    return invoke_contract_function(
        wallet_provider,
        "withdraw",
        args=[to_address, amount_in_wei]
    )

def withdraw_erc20_from_contract(
    wallet_provider: CdpWalletProvider,
    token_address: str,
    to_address: str,
    amount: int
):
    """Withdraw ERC20 tokens from the contract."""
    return invoke_contract_function(
        wallet_provider,
        "withdrawERC20",
        args=[token_address, to_address, amount]
    )


################################################################################
#                         SMALL PARSER HELPERS FOR TOOLS                       #
################################################################################

def parse_deposit_erc20_args(input_str: str):
    """
    Expects: "TOKEN_ADDRESS AMOUNT" (AMOUNT is an integer).
    Example: "0xSomeToken 5000"
    """
    parts = input_str.strip().split()
    if len(parts) != 2:
        return "Error: Provide 'TOKEN_ADDRESS AMOUNT' separated by a space."
    token_addr, amount_str = parts
    try:
        amount_int = int(amount_str)
    except ValueError:
        return "Error: AMOUNT must be an integer."
    return deposit_erc20_to_contract(wallet_provider, token_addr, amount_int)


def parse_erc20_balance_args(input_str: str):
    """
    Expects: "TOKEN_ADDRESS"
    Example: "0xSomeToken"
    """
    token_addr = input_str.strip()
    if not token_addr:
        return "Error: Provide a valid token address."
    return get_contract_erc20_balance(wallet_provider, token_addr)


def parse_withdraw_args(input_str: str):
    """
    Withdraw native ETH from the contract.
    Expects: "TO_ADDRESS AMOUNT_IN_ETH"
    Example: "0xReceiver 0.01"
    We'll parse the float as ETH -> convert to Wei.
    """
    parts = input_str.strip().split()
    if len(parts) != 2:
        return ("Error: Provide 'TO_ADDRESS AMOUNT_IN_ETH'. Example: "
                "'0xReceiver 0.01'")
    to_addr, amount_eth_str = parts
    try:
        val = Decimal(amount_eth_str)
        amount_wei = int(val * Decimal(10**18))
    except:
        return "Error: Amount must be a valid decimal, e.g. 0.01"
    return withdraw_from_contract(wallet_provider, to_addr, amount_wei)


def parse_withdraw_erc20_args(input_str: str):
    """
    Withdraw ERC20 tokens from the contract.
    Expects: "TOKEN_ADDRESS TO_ADDRESS AMOUNT"
    Example: "0xSomeToken 0xReceiver 10000"
    We'll treat AMOUNT as raw integer. The user should handle decimals.
    """
    parts = input_str.strip().split()
    if len(parts) != 3:
        return ("Error: Provide 'TOKEN_ADDRESS TO_ADDRESS AMOUNT'. Example: "
                "'0xSomeToken 0xReceiver 100000'")
    token_addr, to_addr, amount_str = parts
    try:
        amount_int = int(amount_str)
    except:
        return "Error: AMOUNT must be an integer."
    return withdraw_erc20_from_contract(wallet_provider, token_addr, to_addr, amount_int)


################################################################################
#                               AGENT INITIALIZER                              #
################################################################################

def initialize_agent():
    """Initialize the agent with CDP AgentKit and custom tools."""
    llm = ChatOpenAI(model="gpt-4o")

    # Load existing wallet data if present
    wallet_data = None
    if os.path.exists(wallet_data_file):
        with open(wallet_data_file) as f:
            wallet_data = f.read()

    cdp_config = None
    if wallet_data is not None:
        cdp_config = CdpWalletProviderConfig(wallet_data=wallet_data)

    global wallet_provider
    wallet_provider = CdpWalletProvider(cdp_config)

    agentkit = AgentKit(
        AgentKitConfig(
            wallet_provider=wallet_provider,
            action_providers=[
                cdp_api_action_provider(),
                cdp_wallet_action_provider(),
                erc20_action_provider(),
                pyth_action_provider(),
                wallet_action_provider(),
                weth_action_provider(),
                allora_action_provider(),
            ],
        )
    )

    # Save any updates to the wallet (if new keys or addresses were generated)
    wallet_data_json = json.dumps(wallet_provider.export_wallet().to_dict())
    with open(wallet_data_file, "w") as f:
        f.write(wallet_data_json)

    # List all contract-related tools
    custom_contract_tools = [
        # deposit ETH
        Tool(
            name="deposit_eth",
            description=(
                "Deposit ETH into the custom smart contract. "
                "Argument: an ETH float like '0.0001'."
            ),
            func=lambda amount_str: deposit_to_contract(
                wallet_provider, float(amount_str)
            ),
        ),
        # deposit ERC20
        Tool(
            name="deposit_erc20",
            description=(
                "Deposit ERC20 tokens into the custom contract. "
                "Provide 'TOKEN_ADDRESS AMOUNT' (AMOUNT is an integer)."
            ),
            func=parse_deposit_erc20_args,
        ),
        # increment counter
        Tool(
            name="increment_counter",
            description="Increment the counter in the custom smart contract (no arguments).",
            func=lambda _: increment_counter(wallet_provider),
        ),
        # get ETH contract balance
        Tool(
            name="get_contract_balance",
            description="Get the ETH balance (in Wei) of the custom smart contract (no arguments).",
            func=lambda _: get_contract_balance(wallet_provider),
        ),
        # get contract counter
        Tool(
            name="get_contract_counter",
            description="Get the current counter value of the custom smart contract (no arguments).",
            func=lambda _: get_contract_counter(wallet_provider),
        ),
        # get ERC20 token balance
        Tool(
            name="get_contract_erc20_balance",
            description=(
                "Get the ERC20 token balance of the custom contract. Provide a single 'TOKEN_ADDRESS'."
            ),
            func=parse_erc20_balance_args,
        ),
        # withdraw native ETH
        Tool(
            name="withdraw",
            description=(
                "Withdraw native ETH from the custom contract. "
                "Provide 'TO_ADDRESS AMOUNT_IN_ETH'. Example: '0xReceiver 0.01'"
            ),
            func=parse_withdraw_args,
        ),
        # withdraw ERC20
        Tool(
            name="withdraw_erc20",
            description=(
                "Withdraw ERC20 tokens from the custom contract. "
                "Provide 'TOKEN_ADDRESS TO_ADDRESS AMOUNT'. Example: "
                "'0xSomeToken 0xReceiver 1000'"
            ),
            func=parse_withdraw_erc20_args,
        ),
    ]

    # Combine default AgentKit tools with custom ones
    tools = get_langchain_tools(agentkit) + custom_contract_tools

    # Store conversation in memory
    memory = MemorySaver()
    config = {"configurable": {"thread_id": "CDP Agentkit Chatbot Example!"}}

    # Create ReAct agent with a special "state_modifier"
    return create_react_agent(
        llm,
        tools=tools,
        checkpointer=memory,
        state_modifier=(
            "\"You are a high-precision on-chain agent fully integrated with the Coinbase Developer Platform AgentKit. "
            "Your primary role is to interface directly with an Ethereum smart contract deployed at "
            f"{SMART_CONTRACT_ADDRESS} on the Base Sepolia network. This contract supports a set of "
            "functions that allow both ETH and ERC20 interactions, counter management, balance inquiries, "
            "and now withdrawals. Below are the relevant tools, each expecting specific arguments.\n\n"
            "Validate user inputs, convert ETH to Wei, parse integers for ERC20 amounts, "
            "and never leak sensitive wallet data. Provide thorough transaction feedback, including the tx hash. "
            "Always confirm you're on base-sepolia. \""
        ),
    ), config


################################################################################
#                          RUNTIME MODES: Chat / Auto                          #
################################################################################

def run_autonomous_mode(agent_executor, config, interval=10):
    """Optional: run the agent autonomously with specified intervals."""
    print("Starting autonomous mode...")
    while True:
        try:
            thought = (
                "Perform an interesting on-chain action with the provided contract."
            )
            for chunk in agent_executor.stream(
                {"messages": [HumanMessage(content=thought)]}, config
            ):
                if "agent" in chunk:
                    print(chunk["agent"]["messages"][0].content)
                elif "tools" in chunk:
                    print(chunk["tools"]["messages"][0].content)
                print("-------------------")
            time.sleep(interval)
        except KeyboardInterrupt:
            print("Goodbye Agent!")
            sys.exit(0)


def run_chat_mode(agent_executor, config):
    """Run the agent in interactive chat mode."""
    print("Starting chat mode... Type 'exit' to end.")
    while True:
        try:
            user_input = input("\nPrompt: ")
            if user_input.lower() == "exit":
                break

            for chunk in agent_executor.stream(
                {"messages": [HumanMessage(content=user_input)]}, config
            ):
                if "agent" in chunk:
                    print(chunk["agent"]["messages"][0].content)
                elif "tools" in chunk:
                    print(chunk["tools"]["messages"][0].content)
                print("-------------------")
        except KeyboardInterrupt:
            print("Goodbye Agent!")
            sys.exit(0)


def choose_mode():
    """Prompt-based selection: chat or autonomous."""
    while True:
        print("\nAvailable modes:")
        print("1. chat    - Interactive chat mode")
        print("2. auto    - Autonomous action mode")

        choice = input("\nChoose a mode (enter number or name): ").lower().strip()
        if choice in ["1", "chat"]:
            return "chat"
        elif choice in ["2", "auto"]:
            return "auto"
        print("Invalid choice. Please try again.")


def main():
    """Start the chatbot agent."""
    agent_executor, config = initialize_agent()

    # Always start in chat mode
    print("Starting in chat mode... Type 'exit' to end.")
    run_chat_mode(agent_executor=agent_executor, config=config)


if __name__ == "__main__":
    print("Starting Agent...")
    main()
