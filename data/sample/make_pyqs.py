"""Generates 7 years (2019-2025) of SYNTHETIC Operating Systems question papers + a labelled CSV.
Topics follow realistic patterns (some every year, some alternate years, some rare) so the
hot-topic predictor has something to learn. Re-run any time: `python make_pyqs.py`."""
import csv
import random
from pathlib import Path

HERE = Path(__file__).parent

BANK = {
    "Operating system functions": [
        "What are the main functions of an operating system?",
        "Explain the role of the OS as a resource manager.",
        "Discuss the services provided by an operating system to users and programs."],
    "Types of operating systems": [
        "Differentiate between batch, time-sharing and real-time systems.",
        "What is a real-time operating system? Distinguish hard and soft real-time systems.",
        "Explain multiprogramming and how it improves CPU utilisation."],
    "System calls": [
        "What is a system call? Explain the types of system calls with examples.",
        "How does control pass from user mode to kernel mode during a system call?",
        "Explain fork() and exec() system calls."],
    "Process concept": [
        "Draw and explain the process state transition diagram.",
        "Differentiate between a program and a process.",
        "What is a context switch? Why is it considered overhead?"],
    "Process control block": [
        "What is a PCB? List its contents.",
        "Explain the role of the process control block during a context switch."],
    "Scheduling criteria": [
        "Define turnaround time, waiting time and response time.",
        "List and explain the criteria used to compare CPU scheduling algorithms."],
    "FCFS scheduling": [
        "Explain FCFS scheduling and the convoy effect.",
        "Calculate average waiting time using first come first served for the given processes."],
    "SJF scheduling": [
        "Explain SJF scheduling. Why is it called optimal?",
        "Compare SJF and SRTF with an example. How is the next CPU burst predicted?"],
    "Round Robin scheduling": [
        "Explain Round Robin scheduling. What is the effect of time quantum size on performance?",
        "Draw the Gantt chart for round robin with quantum 2 ms and find average turnaround time.",
        "Why is Round Robin suitable for time-sharing systems?"],
    "Priority scheduling": [
        "What is starvation in priority scheduling? How does aging solve it?",
        "Explain preemptive priority scheduling with an example."],
    "Multilevel queue scheduling": [
        "Explain multilevel feedback queue scheduling.",
        "Differentiate multilevel queue and multilevel feedback queue scheduling."],
    "Critical section problem": [
        "What is the critical section problem? State the requirements of a solution.",
        "Explain Peterson's solution for two processes.",
        "What is a race condition? Give an example."],
    "Semaphores": [
        "What is a semaphore? Explain wait and signal operations.",
        "Differentiate between binary and counting semaphores."],
    "Producer consumer problem": [
        "Solve the bounded buffer problem using semaphores.",
        "Explain the producer consumer problem and its solution."],
    "Dining philosophers problem": [
        "Explain the dining philosophers problem and give a deadlock-free solution.",
        "How can deadlock occur among philosophers sharing chopsticks? Suggest remedies."],
    "Monitors": [
        "What is a monitor? How is it better than semaphores?",
        "Explain condition variables used in monitors."],
    "Deadlock conditions": [
        "State the four necessary conditions for deadlock.",
        "Explain deadlock prevention by denying each Coffman condition.",
        "What is a deadlock? Explain with an example."],
    "Resource allocation graph": [
        "Explain the resource allocation graph. Does a cycle always imply deadlock?",
        "Draw a RAG with a cycle but no deadlock."],
    "Bankers algorithm": [
        "Explain the Banker's algorithm with an example. Find whether the system is in a safe state.",
        "Write the safety algorithm used in deadlock avoidance.",
        "Given Max and Allocation matrices, compute Need and find a safe sequence."],
    "Deadlock detection and recovery": [
        "How is deadlock detected using a wait-for graph?",
        "Explain the methods to recover from deadlock."],
    "Paging": [
        "Explain paging with a neat diagram. What is a TLB?",
        "Calculate effective access time with TLB hit ratio 80%.",
        "How does paging eliminate external fragmentation?"],
    "Segmentation": [
        "Explain segmentation with a diagram. How is it different from paging?",
        "What is a segment table? Explain address translation in segmentation."],
    "Virtual memory": [
        "What is virtual memory? Explain demand paging.",
        "Explain the steps in handling a page fault."],
    "Page replacement algorithms": [
        "Compare FIFO, LRU and Optimal page replacement for the given reference string with 3 frames.",
        "What is Belady's anomaly? Explain with an example.",
        "Calculate the number of page faults using LRU for the reference string 7,0,1,2,0,3,0,4."],
    "Thrashing": [
        "What is thrashing? How can it be prevented?",
        "Explain the working set model."],
    "File allocation methods": [
        "Explain contiguous, linked and indexed file allocation methods.",
        "Compare linked allocation and FAT."],
    "Disk scheduling algorithms": [
        "Calculate total head movement using SSTF, SCAN and C-SCAN for the given request queue.",
        "Compare SCAN and C-LOOK disk scheduling.",
        "Explain disk access time and its components."],
    "RAID": [
        "Explain RAID levels 0, 1 and 5.",
        "What is RAID? How does RAID 5 provide fault tolerance?"],
}

# per-topic "appearance pattern": probability of being asked each year
ALWAYS = {"Bankers algorithm", "Page replacement algorithms", "Round Robin scheduling", "Paging", "Disk scheduling algorithms"}
OFTEN = {"Semaphores", "Deadlock conditions", "Critical section problem", "Virtual memory", "SJF scheduling",
         "Process concept", "File allocation methods"}
ALTERNATE_EVEN = {"Thrashing", "Segmentation", "Producer consumer problem", "RAID"}
ALTERNATE_ODD = {"Dining philosophers problem", "Monitors", "Priority scheduling", "System calls"}
RARE = {"Process control block", "Multilevel queue scheduling", "Resource allocation graph", "Operating system functions"}


def p_ask(topic, year):
    if topic in ALWAYS:
        return 0.92
    if topic in OFTEN:
        return 0.6
    if topic in ALTERNATE_EVEN:
        return 0.85 if year % 2 == 0 else 0.1
    if topic in ALTERNATE_ODD:
        return 0.85 if year % 2 == 1 else 0.1
    if topic in RARE:
        return 0.15
    return 0.35


def make(seed=7):
    rng = random.Random(seed)
    labels = []
    for year in range(2019, 2026):
        asked = [t for t in BANK if rng.random() < p_ask(t, year)]
        rng.shuffle(asked)
        lines = [f"I.K. Gujral Punjab Technical University (SAMPLE / SYNTHETIC PAPER)",
                 f"B.Tech CSE — Operating Systems — End Semester Examination {year}",
                 "Time: 3 Hours    Max. Marks: 60", ""]
        sec = {"A": [], "B": [], "C": []}
        for i, t in enumerate(asked):
            q = rng.choice(BANK[t])
            s = "C" if (t in ALWAYS and len(sec["C"]) < 3) else ("B" if len(sec["B"]) < 6 else "A")
            sec[s].append((t, q))
        marks = {"A": 2, "B": 5, "C": 10}
        n = 1
        for s in "ABC":
            lines.append(f"SECTION {s}")
            for t, q in sec[s]:
                lines.append(f"Q{n}. {q} ({marks[s]} marks)")
                labels.append({"text": q, "label": t, "year": year, "marks": marks[s]})
                n += 1
            lines.append("")
        (HERE / f"pyq_os_{year}.txt").write_text("\n".join(lines), encoding="utf-8")
    with open(HERE / "pyq_labels.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["text", "label", "year", "marks"])
        w.writeheader()
        w.writerows(labels)
    print(f"wrote 7 papers, {len(labels)} labelled questions")


if __name__ == "__main__":
    make()
