import csv
import os
import sys
from pathlib import Path
from typing import List, Tuple, Optional

import matplotlib.pyplot as plt


REAL_DURATION_S = 120.0
WORKDAY_SIM_MIN = 8 * 60
SIM_MIN_PER_REAL_S = WORKDAY_SIM_MIN / REAL_DURATION_S

START_HOUR = 8


def read_queue_series(path: Path) -> Tuple[List[float], List[int]]:
    ts_list: List[float] = []
    qlen_list: List[int] = []
    with path.open("r", encoding="utf-8") as f:
        r = csv.DictReader(f)
        for row in r:
            ts_list.append(float(row["ts"]))
            qlen_list.append(int(float(row["queue_len"])))
    return ts_list, qlen_list


def read_customers(path: Path) -> Tuple[List[float], List[float]]:
    wait_times: List[float] = []
    system_times: List[float] = []
    with path.open("r", encoding="utf-8") as f:
        r = csv.DictReader(f)
        for row in r:
            wt = row.get("wait_time", "")
            st = row.get("system_time", "")
            if wt not in ("", "None", None):
                try:
                    wait_times.append(float(wt))
                except ValueError:
                    pass
            if st not in ("", "None", None):
                try:
                    system_times.append(float(st))
                except ValueError:
                    pass
    return wait_times, system_times


def seconds_to_sim_minutes(real_s: float) -> float:
    return real_s * SIM_MIN_PER_REAL_S


def sim_minutes_to_clock_labels(sim_minutes: List[float]) -> List[str]:
    labels = []
    for m in sim_minutes:
        total_minutes = START_HOUR * 60 + int(round(m))
        hh = (total_minutes // 60) % 24
        mm = total_minutes % 60
        labels.append(f"{hh:02d}:{mm:02d}")
    return labels


def make_queue_plot(run_dir: Path) -> None:
    qfile = run_dir / "queue_series.csv"
    if not qfile.exists():
        print(f"[WARN] Nema {qfile}")
        return

    ts_list, qlen_list = read_queue_series(qfile)
    if not ts_list:
        print(f"[WARN] Prazan {qfile}")
        return

    ts0 = ts_list[0]
    real_elapsed = [t - ts0 for t in ts_list]
    sim_elapsed_min = [seconds_to_sim_minutes(s) for s in real_elapsed]

    plt.figure()
    plt.plot(sim_elapsed_min, qlen_list)
    plt.xlabel("Vrijeme (simulacijsko, minute od 08:00)")
    plt.ylabel("Veličina reda (queue_len)")
    plt.title(f"Duljina reda kroz radni dan ({run_dir.name})")

    tick_sim_minutes = [0, 120, 240, 360, 480]
    tick_labels = sim_minutes_to_clock_labels(tick_sim_minutes)
    plt.xticks(tick_sim_minutes, tick_labels)

    out = run_dir / "queue_length.png"
    plt.savefig(out, dpi=160, bbox_inches="tight")
    plt.close()
    print(f"[OK] Spremljeno: {out}")


def make_hist_plots(run_dir: Path) -> None:
    cfile = run_dir / "customers.csv"
    if not cfile.exists():
        print(f"[WARN] Nema {cfile}")
        return

    wait_s, system_s = read_customers(cfile)
    if not wait_s and not system_s:
        print(f"[WARN] Nema wait_time/system_time u {cfile}")
        return

    wait_min = [seconds_to_sim_minutes(x) for x in wait_s]
    system_min = [seconds_to_sim_minutes(x) for x in system_s]

    if wait_min:
        plt.figure()
        plt.hist(wait_min, bins=20)
        plt.xlabel("Čekanje (simulacijske minute)")
        plt.ylabel("Broj klijenata")
        plt.title(f"Histogram čekanja (wait_time) ({run_dir.name})")
        out = run_dir / "hist_wait_time.png"
        plt.savefig(out, dpi=160, bbox_inches="tight")
        plt.close()
        print(f"[OK] Spremljeno: {out}")

    if system_min:
        plt.figure()
        plt.hist(system_min, bins=20)
        plt.xlabel("Vrijeme u sustavu (simulacijske minute)")
        plt.ylabel("Broj klijenata")
        plt.title(f"Histogram vremena u sustavu (system_time) ({run_dir.name})")
        out = run_dir / "hist_system_time.png"
        plt.savefig(out, dpi=160, bbox_inches="tight")
        plt.close()
        print(f"[OK] Spremljeno: {out}")


def usage() -> None:
    print(
        "Upotreba:\n"
        "  python -m src.plot_results queue <run_dir1> [run_dir2 ...]\n"
        "  python -m src.plot_results hist  <run_dir1> [run_dir2 ...]\n\n"
        "Gdje je run_dir folder koji sadrži queue_series.csv i customers.csv.\n"
        "Skripta sprema PNG u isti run_dir."
    )


def main():
    if len(sys.argv) < 3:
        usage()
        sys.exit(1)

    mode = sys.argv[1].strip().lower()
    dirs = [Path(p) for p in sys.argv[2:]]

    for d in dirs:
        if not d.exists() or not d.is_dir():
            print(f"[WARN] Preskačem (nije folder): {d}")
            continue

        if mode == "queue":
            make_queue_plot(d)
        elif mode == "hist":
            make_hist_plots(d)
        else:
            usage()
            sys.exit(1)


if __name__ == "__main__":
    main()
