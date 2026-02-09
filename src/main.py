import asyncio
import sys

from src.agents.bank import BankAgent
from src.agents.teller import TellerAgent


def parse_scenario(argv: list[str]) -> str:
    if len(argv) < 2:
        return "normal"
    s = argv[1].strip().lower()
    if s in ("normal", "pocetak_mjeseca"):
        return s
    print("Nepoznat scenarij. Koristi: normal | pocetak_mjeseca")
    print("Pokrećem default: normal")
    return "normal"


async def main():
    scenario = parse_scenario(sys.argv)

    password = "password"
    bank_jid = "bank@localhost"

    teller_jids = [
        "teller1@localhost",
        "teller2@localhost",
        "teller3@localhost",
        "teller4@localhost",
    ]

    bank = BankAgent(
        bank_jid,
        password,
        teller_jids=teller_jids,
        scenario=scenario,
        real_duration_s=120.0,
        tick_real_s=0.5,
    )

    tellers = [TellerAgent(tj, password, bank_jid=bank_jid) for tj in teller_jids]

    for t in tellers:
        await t.start(auto_register=True)
    await bank.start(auto_register=True)

    for _ in range(280):
        if not bank.is_alive():
            break
        await asyncio.sleep(0.5)

    for t in tellers:
        if t.is_alive():
            await t.stop()

    await asyncio.sleep(1.0)


if __name__ == "__main__":
    asyncio.run(main())
