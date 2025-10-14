import asyncio
from client import MCPClient


async def main():
    client = MCPClient()
    try:
        await client.register_all_servers()
        await client.run()
    finally:
        await client.cleanup()


if __name__ == "__main__":
    asyncio.run(main())
