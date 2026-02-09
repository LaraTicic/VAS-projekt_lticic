import asyncio
import random
import time
from collections import deque
from typing import Deque, Dict, Set

from spade.agent import Agent
from spade.behaviour import CyclicBehaviour, PeriodicBehaviour, OneShotBehaviour
from spade.message import Message

from src.sim.metrics import Metrics


def poisson_knuth(lmbda: float) -> int:
    if lmbda <= 0:
        return 0
    L = random.random()
    k = 0
    p = 1.0
    import math
    threshold = math.exp(-lmbda)
    while p > threshold:
        k += 1
        p *= random.random()
    return k - 1


class BankAgent(Agent):
    WORKDAY_SIM_MINUTES = 8 * 60
    START_HOUR = 8
    END_HOUR = 16

    LUNCH1_START = (11 * 60) + 30 
    LUNCH1_END = (12 * 60)
    LUNCH2_START = (12 * 60)
    LUNCH2_END = (12 * 60) + 30

    def __init__(
        self,
        jid: str,
        password: str,
        teller_jids: list[str],
        scenario: str,
        real_duration_s: float = 120.0,
        tick_real_s: float = 0.5,
    ):
        super().__init__(jid, password)
        self.teller_jids = teller_jids
        self.scenario = scenario.lower()
        self.real_duration_s = real_duration_s
        self.tick_real_s = tick_real_s

        self.sim_ended = False
        self.start_wall_ts: float | None = None
        self.end_wall_ts: float | None = None

        self.queue: Deque[str] = deque()
        self.free_tellers: Set[str] = set(teller_jids)
        self.busy_customer_by_teller: Dict[str, str] = {}

        self.metrics = Metrics()

        self.spawned_customers = [] 

        self.lunch_group_1 = set(teller_jids[:2])
        self.lunch_group_2 = set(teller_jids[2:4])

    def now(self) -> float:
        return time.time()

    def sim_minutes_elapsed(self) -> float:
        if self.start_wall_ts is None:
            return 0.0
        elapsed_real = self.now() - self.start_wall_ts
        return (elapsed_real / self.real_duration_s) * self.WORKDAY_SIM_MINUTES

    def sim_minute_of_day(self) -> float:
        return (self.START_HOUR * 60) + self.sim_minutes_elapsed()

    def is_bank_open(self) -> bool:
        return self.sim_minutes_elapsed() < self.WORKDAY_SIM_MINUTES and not self.sim_ended

    def is_teller_available_now(self, teller_jid: str) -> bool:
        t = self.sim_minute_of_day()
        if self.LUNCH1_START <= t < self.LUNCH1_END and teller_jid in self.lunch_group_1:
            return False
        if self.LUNCH2_START <= t < self.LUNCH2_END and teller_jid in self.lunch_group_2:
            return False
        return True

    def update_free_tellers_by_schedule(self) -> None:
        for t in self.teller_jids:
            available = self.is_teller_available_now(t)
            busy = t in self.busy_customer_by_teller
            if not available:
                self.free_tellers.discard(t)
            else:
                if not busy:
                    self.free_tellers.add(t)

    def arrival_rate_per_sim_minute(self) -> float:
        t = self.sim_minute_of_day()

        if self.scenario == "pocetak_mjeseca":
            if t < 10 * 60:
                return 0.95
            elif t < 12 * 60:
                return 0.75
            else:
                return 0.45

        if t < 10 * 60:
            return 0.55
        elif t < 12 * 60:
            return 0.40
        else:
            return 0.28

    def sim_minutes_per_real_second(self) -> float:
        return self.WORKDAY_SIM_MINUTES / self.real_duration_s

    def service_time_real_seconds(self) -> float:
        sim_min = random.uniform(8.0, 22.0)
        return sim_min / self.sim_minutes_per_real_second()

    async def try_dispatch(self, beh) -> None:
        self.update_free_tellers_by_schedule()

        while self.free_tellers and self.queue:
            teller = next(iter(self.free_tellers))
            if not self.is_teller_available_now(teller):
                self.free_tellers.discard(teller)
                continue

            self.free_tellers.discard(teller)
            customer = self.queue.popleft()
            self.busy_customer_by_teller[teller] = customer

            self.metrics.set_start_service(customer, self.now(), teller)

            serve = Message(to=teller)
            serve.body = f"SERVE|{customer}"
            await beh.send(serve)

            self.metrics.add_queue_point(self.now(), len(self.queue))

    class ListenBehaviour(CyclicBehaviour):
        async def run(self):
            msg = await self.receive(timeout=1)
            if not msg:
                return

            body = msg.body
            sender = str(msg.sender)

            if self.agent.sim_ended and body.startswith("ARRIVE|"):
                return

            if body.startswith("ARRIVE|"):
                customer_jid = body.split("|", 1)[1]
                ts = self.agent.now()
                self.agent.metrics.ensure_customer(customer_jid, ts)

                self.agent.queue.append(customer_jid)
                self.agent.metrics.add_queue_point(ts, len(self.agent.queue))

                await self.agent.try_dispatch(self)

            elif body.startswith("DONE|"):
                parts = body.split("|")
                customer_jid = parts[1]
                teller_jid = parts[3] if len(parts) >= 4 else sender

                self.agent.metrics.set_end(customer_jid, self.agent.now())

                self.agent.busy_customer_by_teller.pop(teller_jid, None)

                if self.agent.is_teller_available_now(teller_jid) and not self.agent.sim_ended:
                    self.agent.free_tellers.add(teller_jid)

                finish = Message(to=customer_jid)
                finish.body = "FINISH"
                await self.send(finish)

                await self.agent.try_dispatch(self)

    class ArrivalGenerator(PeriodicBehaviour):
        async def run(self):
            if not self.agent.is_bank_open():
                return
            if self.agent.end_wall_ts is not None and (self.agent.end_wall_ts - self.agent.now()) <= 10.0:
                self.agent.metrics.add_queue_point(self.agent.now(), len(self.agent.queue))
                return

            self.agent.update_free_tellers_by_schedule()

            delta_sim_minutes = self.agent.sim_minutes_per_real_second() * self.agent.tick_real_s

            lam_per_min = self.agent.arrival_rate_per_sim_minute()
            lam_tick = lam_per_min * delta_sim_minutes

            k = poisson_knuth(lam_tick)

            cap = 3 if self.agent.scenario == "normal" else 5
            k = min(k, cap)

            if k <= 0:
                self.agent.metrics.add_queue_point(self.agent.now(), len(self.agent.queue))
                return

            from src.agents.customer import CustomerAgent

            for _ in range(k):
                if self.agent.sim_ended:
                    return

                idx = random.randint(1000, 9999)
                customer_jid = f"customer{idx}@localhost"
                customer_pass = "password"
                service_time_real = self.agent.service_time_real_seconds()

                c = CustomerAgent(
                    customer_jid,
                    customer_pass,
                    bank_jid=str(self.agent.jid),
                    service_time=service_time_real,
                )
                await c.start(auto_register=True)

                if self.agent.sim_ended:
                    try:
                        await c.stop()
                    except Exception:
                        pass
                    return

                self.agent.spawned_customers.append(c)
                await asyncio.sleep(0.02)

            self.agent.metrics.add_queue_point(self.agent.now(), len(self.agent.queue))

    class Stopper(OneShotBehaviour):
        async def run(self):
            await asyncio.sleep(self.agent.real_duration_s)

            print("[BANK] Simulacija gotova -> spremam metrike u results/")

            self.agent.sim_ended = True

            all_customer_jids = set(self.agent.metrics.unfinished_customers())
            all_customer_jids.update(self.agent.queue)
            all_customer_jids.update(self.agent.busy_customer_by_teller.values())

            for cjid in all_customer_jids:
                m = Message(to=cjid)
                m.body = "CLOSE"
                await self.send(m)

            await asyncio.sleep(0.5)

            for c in list(self.agent.spawned_customers):
                try:
                    if c.is_alive():
                        await c.stop()
                except Exception:
                    pass

            self.agent.metrics.write_csv("results")

            for t in self.agent.teller_jids:
                m = Message(to=t)
                m.body = "STOP"
                await self.send(m)

            await asyncio.sleep(0.3)
            await self.agent.stop()

    async def setup(self):
        print(f"[BANK] setup() pozvan: {self.jid} | scenarij={self.scenario}")
        self.start_wall_ts = self.now()
        self.end_wall_ts = self.start_wall_ts + self.real_duration_s

        self.add_behaviour(self.ListenBehaviour())
        self.add_behaviour(self.ArrivalGenerator(period=self.tick_real_s))
        self.add_behaviour(self.Stopper())
