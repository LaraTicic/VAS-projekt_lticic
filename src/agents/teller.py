import asyncio
from spade.agent import Agent
from spade.behaviour import CyclicBehaviour
from spade.message import Message


class TellerAgent(Agent):
    def __init__(self, jid, password, bank_jid: str):
        super().__init__(jid, password)
        self.bank_jid = bank_jid

    class ListenBehaviour(CyclicBehaviour):
        async def run(self):
            msg = await self.receive(timeout=10)
            if not msg:
                return

            body = msg.body
            sender = str(msg.sender)
            print(f"[TELLER {self.agent.jid}] primio od {sender}: {body}")

            if body == "STOP":
                print(f"[TELLER {self.agent.jid}] STOP -> gasim se")
                await self.agent.stop()
                return

            if body.startswith("SERVE|"):
                customer_jid = body.split("|", 1)[1]
                call = Message(to=customer_jid)
                call.body = f"CALL|{self.agent.jid}"
                await self.send(call)

            elif body.startswith("REQUEST|"):
                parts = body.split("|")
                customer_jid = parts[1]
                service_time = float(parts[2])

                await asyncio.sleep(service_time)

                done = Message(to=self.agent.bank_jid)
                done.body = f"DONE|{customer_jid}|{service_time}|{self.agent.jid}"
                await self.send(done)

    async def setup(self):
        print(f"[TELLER] setup() pozvan: {self.jid}")
        self.add_behaviour(self.ListenBehaviour())
