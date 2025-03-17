# Custom Smart Contract Actions with Coinbase AgentKit

This project demonstrates how to extend Coinbase AgentKit to interact with custom smart contracts on EVM-compatible blockchains. The implementation modifies the standard AgentKit chatbot to enable direct interaction with a smart contract deployed on Base Sepolia.

## Features

- Custom smart contract integration with Coinbase AgentKit
- Direct contract function calls through LangChain tools
- Support for both read and write contract operations
- ETH and ERC20 token deposit capabilities
- Contract balance and counter value queries

## Smart Contract Details

Contract Address: `0xa633656593bB24252A55A468146fe9536eA899cB` (Base Sepolia)

Supported contract functions:
- `deposit()` - Payable function to send ETH to the contract
- `depositERC20(address tokenAddress, uint256 amount)` - Deposit ERC20 tokens
- `incrementCounter()` - Increment a counter value
- `getBalance()` - Get contract's ETH balance
- `getCounter()` - Get current counter value
- `getERC20Balance(address token)` - Get contract's ERC20 token balance

## Demo Transactions

The following transactions were successfully executed:

### Deposit ETH to the contract

```
Successfully called deposit: Transaction hash: 0x0caae562151b58e1669aaac317a2a27b4a8e3246fedf230dc9e4defec685f52e
```

### Increment Counter

```
Successfully called incrementCounter. Transaction hash: 0x273a8ce3dad84de850f4e408eaa69b382018e574ee698e9a8d84b9df7a383821
```

### Get Counter Value

```
> get counter
1
```

## Implementation Details

The project extends the standard Coinbase AgentKit chatbot with:

1. Contract ABI definition
2. Function encoding utilities
3. Transaction parameter building
4. Custom LangChain tools for contract interaction
5. Dedicated wrapper functions for each contract method

Key files:
- `chatbot.py` - Main implementation with smart contract integration

## Getting Started

### Prerequisites

- Python 3.9+
- Poetry (Python package manager)
- Access to Base Sepolia RPC
- ETH in your Base Sepolia wallet

### Installation

1. Clone the repository:
```bash
git clone https://github.com/0x0Glitch/custom-action-cdp.git
cd custom-action-cdp
```

2. Install dependencies:
```bash
poetry install
```

3. Set up your environment variables:
```bash
cp .env.example .env
# Edit .env with your configuration
```

4. Run the chatbot:
```bash
poetry run python agentkit/python/examples/langchain-cdp-chatbot/chatbot.py
```

## How It Works

1. The chatbot initializes with the Coinbase AgentKit and loads the custom smart contract ABI
2. Custom tools are registered with LangChain for each contract function
3. Contract function calls are encoded using Web3.py
4. Transactions are signed and sent using the CDP Wallet Provider
5. Read operations use the `read_contract` method, while write operations use `send_transaction`

## License

This project is licensed under the MIT License - see the LICENSE file for details.
