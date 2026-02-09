from spade.agent import Agent
from spade.behaviour import OneShotBehaviour, CyclicBehaviour
from spade.message import Message


class CustomerAgent(Agent):
    def __init__(self, jid, password, bank_jid: str, service_time: float):
        super().__init__(jid, password)
        self.bank_jid = bank_jid
        self.service_time = service_time  # real seconds (scaled from sim minutes)

    class ArriveBehaviour(OneShotBehaviour):
        async def run(self):
            msg = Message(to=self.agent.bank_jid)
            msg.body = f"ARRIVE|{self.agent.jid}"
            await self.send(msg)
            print(f"[CUSTOMER] {self.agent.jid} -> BANK: {msg.body}")

    class ListenBehaviour(CyclicBehaviour):
        async def run(self):
            msg = await self.receive(timeout=60)
            if not msg:
                return

            print(f"[CUSTOMER] {self.agent.jid} primio od {msg.sender}: {msg.body}")

            if msg.body.startswith("CALL|"):
                teller_jid = msg.body.split("|", 1)[1]
                req = Message(to=teller_jid)
                req.body = f"REQUEST|{self.agent.jid}|{self.agent.service_time}"
                await self.send(req)
                print(f"[CUSTOMER] {self.agent.jid} -> TELLER: {req.body}")

            elif msg.body == "FINISH":
                print(f"[CUSTOMER] {self.agent.jid} završio i odlazi.")
                await self.agent.stop()

            elif msg.body == "CLOSE":
                print(f"[CUSTOMER] {self.agent.jid} banka zatvorena -> odlazi.")
                await self.agent.stop()

    async def setup(self):
        print(f"[CUSTOMER] setup() pozvan: {self.jid}")
        self.add_behaviour(self.ArriveBehaviour())
        self.add_behaviour(self.ListenBehaviour())
