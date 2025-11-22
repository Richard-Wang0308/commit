import os
import sys
import argparse
import asyncio

from typing import Any, Tuple

from dotenv import load_dotenv
import bittensor as bt
from bittensor.core.errors import MetadataError
from substrateinterface import SubstrateInterface

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.append(BASE_DIR)

from config.config_loader import load_config

# ----------------------------------------------------------------------------
# 1. CONFIG & ARGUMENT PARSING
# ----------------------------------------------------------------------------

def parse_arguments() -> argparse.Namespace:
    """
    Parses command line arguments and merges with config defaults.

    Returns:
        argparse.Namespace: The combined configuration object.
    """
    parser = argparse.ArgumentParser()
    # Add override arguments for network.
    parser.add_argument('--network', default=os.getenv('SUBTENSOR_NETWORK'), help='Network to use')
    # Adds override arguments for netuid.
    parser.add_argument('--netuid', type=int, default=68, help="The chain subnet uid.")
    # Bittensor standard argument additions.
    bt.subtensor.add_args(parser)
    bt.logging.add_args(parser)
    bt.wallet.add_args(parser)

    # Parse combined config
    config = bt.config(parser)

    # Load protein selection params
    config.update(load_config())

    # Final logging dir
    config.full_path = os.path.expanduser(
        "{}/{}/{}/netuid{}/{}".format(
            config.logging.logging_dir,
            config.wallet.name,
            config.wallet.hotkey_str,
            config.netuid,
            'miner',
        )
    )

    # Ensure the logging directory exists.
    os.makedirs(config.full_path, exist_ok=True)
    return config

# ----------------------------------------------------------------------------
# 2. LOGGING SETUP
# ----------------------------------------------------------------------------

def setup_logging(config: argparse.Namespace) -> None:
    """
    Sets up Bittensor logging.

    Args:
        config (argparse.Namespace): The miner configuration object.
    """
    bt.logging(config=config, logging_dir=config.full_path)
    bt.logging.info(f"Running miner for subnet: {config.netuid} on network: {config.subtensor.network} with config:")
    bt.logging.info(config)


# ----------------------------------------------------------------------------
# 3. BITTENSOR & NETWORK SETUP
# ----------------------------------------------------------------------------

async def setup_bittensor_objects(config: argparse.Namespace) -> Tuple[Any, Any, Any, int]:
    """
    Initializes wallet, subtensor, and metagraph. Fetches the epoch length
    and calculates the miner UID.

    Args:
        config (argparse.Namespace): The miner configuration object.

    Returns:
        tuple: A 5-element tuple of
            (wallet, subtensor, metagraph, miner_uid, epoch_length).
    """
    bt.logging.info("Setting up Bittensor objects.")

    # Initialize wallet
    wallet = bt.wallet(config=config)
    bt.logging.info(f"Wallet: {wallet}")

    # Initialize subtensor (asynchronously)
    try:
        subtensor = await bt.async_subtensor(network=config.network).__aenter__()
        bt.logging.info(f"Connected to subtensor network: {config.network}")
            
        # Sync metagraph
        metagraph = await subtensor.metagraph(config.netuid)
        await metagraph.sync()
        bt.logging.info(f"Metagraph synced successfully.")

        bt.logging.info(f"Subtensor: {subtensor}")
        bt.logging.info(f"Metagraph synced: {metagraph}")

        # Get miner UID
        miner_uid = metagraph.hotkeys.index(wallet.hotkey.ss58_address)
        bt.logging.info(f"Miner UID: {miner_uid}")

        # Query epoch length
        node = SubstrateInterface(url=config.network)
        # Set epoch_length to tempo + 1

        return wallet, subtensor, metagraph, miner_uid
    except Exception as e:
        bt.logging.error(f"Failed to setup Bittensor objects: {e}")
        bt.logging.error("Please check your network connection and the subtensor network status")
        raise


async def run_miner(config: argparse.Namespace) -> None:
    """
    The main mining loop, orchestrating:
      - Bittensor objects initialization
      - Model initialization
      - Fetching new proteins each epoch
      - Running inference and submissions
      - Periodically syncing metagraph

    Args:
        config (argparse.Namespace): The miner configuration object.
    """

    # 1) Setup wallet, subtensor, metagraph, etc.
    wallet, subtensor, metagraph, miner_uid = await setup_bittensor_objects(config)

    # owner="Richard-Wang0308"
    owner="alcantara0123"
    # repo="nova-blueprint-miner"
    # repo="nova-blueprint-miner-v2"
    # repo="nova-miner"
    repo="nova-1119"
    branch="master"

    try: 
        commitment_status = await subtensor.set_commitment(
            wallet=wallet,
            netuid=68,
            data=f"{owner}/{repo}@{branch}"
        )
        bt.logging.info(f"Chain commitment status: {commitment_status}")
        print(f"Chain commitment status: {commitment_status}")
    except MetadataError:
        bt.logging.info("Too soon to commit again. Will keep looking for better candidates.")
        return

    # 4) If chain commitment success, upload to GitHub
    if commitment_status:
        bt.logging.info(f"Commitment set successfully for ({owner}/{repo}@{branch})")
        print(f"Commitment set successfully for ({owner}/{repo}@{branch})")
            


# ----------------------------------------------------------------------------
# 7. ENTRY POINT
# ----------------------------------------------------------------------------

async def main() -> None:
    """
    Main entry point for asynchronous execution of the miner logic.
    """
    config = parse_arguments()
    setup_logging(config)
    await run_miner(config)


if __name__ == "__main__":
    load_dotenv()
    asyncio.run(main())
