import csv
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, List


@dataclass
class CustomerRecord:
    customer_jid: str
    arrival_ts: float
    start_service_ts: float | None = None
    end_ts: float | None = None
    teller_jid: str | None = None

    @property
    def wait_time(self) -> float | None:
        if self.start_service_ts is None:
            return None
        return self.start_service_ts - self.arrival_ts

    @property
    def system_time(self) -> float | None:
        if self.end_ts is None:
            return None
        return self.end_ts - self.arrival_ts


class Metrics:
    def __init__(self) -> None:
        self.customers: Dict[str, CustomerRecord] = {}
        self.queue_series: List[tuple[float, int]] = []

    def ensure_customer(self, customer_jid: str, arrival_ts: float) -> None:
        if customer_jid not in self.customers:
            self.customers[customer_jid] = CustomerRecord(customer_jid=customer_jid, arrival_ts=arrival_ts)

    def set_start_service(self, customer_jid: str, ts: float, teller_jid: str) -> None:
        self.customers[customer_jid].start_service_ts = ts
        self.customers[customer_jid].teller_jid = teller_jid

    def set_end(self, customer_jid: str, ts: float) -> None:
        self.customers[customer_jid].end_ts = ts

    def add_queue_point(self, ts: float, qlen: int) -> None:
        self.queue_series.append((ts, qlen))

    def unfinished_customers(self) -> list[str]:
        return [jid for jid, rec in self.customers.items() if rec.end_ts is None]

    def count_unserved(self) -> int:
        n = 0
        for rec in self.customers.values():
            if rec.start_service_ts is None or rec.end_ts is None:
                n += 1
        return n

    def write_csv(self, out_dir: str = "results") -> None:
        Path(out_dir).mkdir(parents=True, exist_ok=True)

        cust_path = Path(out_dir) / "customers.csv"
        with cust_path.open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(
                f,
                fieldnames=[
                    "customer_jid", "arrival_ts", "start_service_ts", "end_ts",
                    "teller_jid", "wait_time", "system_time"
                ],
            )
            w.writeheader()
            for rec in self.customers.values():
                row = asdict(rec)
                row["wait_time"] = rec.wait_time
                row["system_time"] = rec.system_time
                w.writerow(row)

        q_path = Path(out_dir) / "queue_series.csv"
        with q_path.open("w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["ts", "queue_len"])
            w.writerows(self.queue_series)

        summary_path = Path(out_dir) / "summary.csv"
        with summary_path.open("w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["metric", "value"])
            w.writerow(["unserved_customers", self.count_unserved()])
            w.writerow(["total_customers", len(self.customers)])
