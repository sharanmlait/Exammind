# Operating Systems — Class Notes (sample notes for the ExamMind demo)

## Unit I: Introduction

### Operating system functions
An operating system is a program that acts as an intermediary between the user and the computer hardware. Its main functions are process management, memory management, file management, device (I/O) management, security and protection, and providing a user interface. The OS also allocates resources such as CPU time, memory and I/O devices fairly among competing programs. It hides hardware complexity by providing abstractions like processes, files and virtual memory.

### Types of operating systems
A batch operating system groups similar jobs into batches and runs them without user interaction. A multiprogramming operating system keeps several jobs in memory at once so the CPU always has something to run, which increases CPU utilisation. A time-sharing operating system is an extension of multiprogramming in which the CPU switches between users so quickly that each user feels they have their own machine. A real-time operating system is an OS that must respond to events within strict time limits; hard real-time systems (airbag controllers) cannot miss deadlines, while soft real-time systems (video streaming) can tolerate occasional delays. Distributed operating systems manage a group of networked computers and make them appear as a single system.

### System calls
A system call is the programmatic interface through which a user program requests a service from the kernel. When a process makes a system call, the CPU switches from user mode to kernel mode using a trap instruction. System calls are grouped into process control (fork, exec, exit, wait), file management (open, read, write, close), device management (ioctl), information maintenance (getpid, time) and communication (pipe, shmget, socket). Parameters are passed to the kernel through registers, a block in memory, or the stack.

### Process concept
A process is a program in execution. A program is a passive entity stored on disk, while a process is an active entity with a program counter, registers, stack, heap, data section and text section. A process moves through five states: new, ready, running, waiting (blocked) and terminated. The long-term scheduler decides which jobs are admitted to the ready queue, the short-term scheduler picks the next process for the CPU, and the medium-term scheduler swaps processes out of memory to reduce the degree of multiprogramming. A context switch is the act of saving the state of the current process and loading the saved state of the next process; it is pure overhead because no useful work is done during the switch.

### Process control block
The process control block (PCB) is a data structure in the kernel that stores all information about a process. A PCB contains the process ID, process state, program counter, CPU registers, CPU-scheduling information (priority, queue pointers), memory-management information (page tables, base and limit registers), accounting information (CPU time used) and I/O status information (list of open files). During a context switch the OS saves the running process's state into its PCB and restores the next process's state from its PCB.

--- page 2 ---

## Unit II: CPU Scheduling

### Scheduling criteria
CPU scheduling decides which process in the ready queue gets the CPU next. The main scheduling criteria are CPU utilisation, throughput (processes completed per unit time), turnaround time, waiting time and response time. A good scheduler maximises CPU utilisation and throughput and minimises turnaround, waiting and response time.
Turnaround time = Completion time - Arrival time
Waiting time = Turnaround time - Burst time
Response time = Time of first CPU allocation - Arrival time

### FCFS scheduling
First-Come, First-Served (FCFS) scheduling is the simplest scheduling algorithm, where the process that arrives first is served first using a FIFO queue. FCFS is non-preemptive. Its main drawback is the convoy effect: short processes wait behind one long CPU-bound process, which increases average waiting time.

### SJF scheduling
Shortest Job First (SJF) scheduling is an algorithm that selects the process with the smallest next CPU burst. SJF gives the minimum average waiting time for a given set of processes, so it is optimal. The preemptive version is called Shortest Remaining Time First (SRTF). The difficulty is that the length of the next CPU burst is not known in advance; it is predicted using exponential averaging.
Predicted burst: T(n+1) = a * t(n) + (1 - a) * T(n)
SJF can cause starvation of long processes.

### Round Robin scheduling
Round Robin (RR) scheduling is a preemptive algorithm designed for time-sharing systems, in which each process gets a small unit of CPU time called a time quantum (usually 10-100 ms). If the process does not finish within the quantum, it is preempted and put at the back of the ready queue. If the quantum is very large, RR behaves like FCFS; if it is very small, too much time is wasted on context switches. RR gives good response time and no starvation.

### Priority scheduling
Priority scheduling is an algorithm in which each process is assigned a priority and the CPU is given to the highest-priority process. It can be preemptive or non-preemptive. Its major problem is starvation (indefinite blocking) of low-priority processes. The solution is aging, which gradually increases the priority of processes that wait for a long time.

### Multilevel queue scheduling
Multilevel queue scheduling divides the ready queue into several separate queues, for example foreground (interactive) and background (batch) queues, each with its own scheduling algorithm. Processes are permanently assigned to one queue. In multilevel feedback queue scheduling, processes can move between queues: a process that uses too much CPU time is moved to a lower-priority queue, and a process that waits too long is moved to a higher-priority queue, which prevents starvation.

--- page 3 ---

## Unit III: Process Synchronization

### Critical section problem
A critical section is a segment of code in which a process accesses shared data such as variables, files or tables. A race condition occurs when several processes access shared data concurrently and the final result depends on the order of execution. A solution to the critical section problem must satisfy three requirements: mutual exclusion (only one process in its critical section at a time), progress (if no process is in the critical section, the selection of the next one cannot be postponed indefinitely), and bounded waiting (there is a limit on how many times other processes can enter before a waiting process). Peterson's solution is a classic software solution for two processes that uses a turn variable and a flag array.

### Semaphores
A semaphore is an integer synchronisation variable that is accessed only through two atomic operations: wait() (also called P or down) and signal() (also called V or up). wait() decrements the semaphore and blocks the process if the value becomes negative; signal() increments it and wakes up a waiting process. A binary semaphore (mutex) takes only the values 0 and 1, while a counting semaphore can take any non-negative value and is used to control access to a resource with multiple instances. Incorrect use of semaphores can cause deadlock and starvation.

### Producer consumer problem
The producer consumer problem, also called the bounded buffer problem, has a producer that puts items into a fixed-size buffer and a consumer that removes them. The producer must wait when the buffer is full and the consumer must wait when the buffer is empty. It is solved using three semaphores: mutex (initialised to 1) for mutual exclusion on the buffer, empty (initialised to n) to count empty slots, and full (initialised to 0) to count filled slots.

### Dining philosophers problem
The dining philosophers problem is a classic synchronisation problem with five philosophers sitting around a table with five chopsticks; each needs both the left and the right chopstick to eat. If every philosopher picks up the left chopstick at the same time, deadlock occurs. Solutions include allowing at most four philosophers at the table, picking up both chopsticks only if both are available, or using an asymmetric rule where odd philosophers pick the left chopstick first and even philosophers pick the right one first.

### Monitors
A monitor is a high-level synchronisation construct that contains shared variables, procedures that operate on them, and initialisation code; only one process can be active inside a monitor at a time. Monitors use condition variables with two operations, x.wait() and x.signal(), to let processes wait for specific conditions. Monitors are easier and less error-prone to use than semaphores because mutual exclusion is guaranteed by the compiler.

--- page 4 ---

## Unit IV: Deadlocks

### Deadlock conditions
A deadlock is a situation in which a set of processes are blocked because each process is holding a resource and waiting for a resource held by another process in the set. Four necessary conditions (Coffman conditions) must hold at the same time for a deadlock: mutual exclusion, hold and wait, no preemption, and circular wait. Deadlock prevention works by making sure at least one of these four conditions can never hold, for example by imposing a total ordering on resource types to prevent circular wait.

### Resource allocation graph
A resource allocation graph (RAG) is a directed graph used to describe deadlocks, with process nodes (circles) and resource nodes (rectangles with dots for instances). A request edge goes from a process to a resource, and an assignment edge goes from a resource to a process. If the graph has no cycle, there is no deadlock. If there is a cycle and each resource has only one instance, a deadlock exists; if resources have several instances, a cycle means a deadlock is possible but not certain.

### Bankers algorithm
The Banker's algorithm is a deadlock avoidance algorithm that grants a resource request only if the system stays in a safe state. A safe state is a state in which there exists a safe sequence of all processes such that each process can finish using the currently available resources plus those held by earlier processes. The algorithm uses the Available vector and the Max, Allocation and Need matrices.
Need = Max - Allocation
The safety algorithm repeatedly finds a process whose Need is less than or equal to Work, then adds its Allocation to Work, until all processes finish (safe) or no such process exists (unsafe). The resource-request algorithm pretends to allocate the request and runs the safety algorithm to decide whether to grant it.

### Deadlock detection and recovery
Deadlock detection lets deadlocks occur and then finds them, using a wait-for graph for single-instance resources or a Banker's-like detection algorithm for multiple instances. Recovery can be done by process termination (abort all deadlocked processes, or abort one at a time until the cycle is broken) or by resource preemption, which involves selecting a victim, rolling the process back, and preventing starvation so the same process is not always chosen as the victim.

--- page 5 ---

## Unit V: Memory Management

### Paging
Paging is a memory-management scheme that allows the physical address space of a process to be non-contiguous. Physical memory is divided into fixed-size blocks called frames and logical memory into blocks of the same size called pages. The page table maps each page number to a frame number. A logical address is divided into a page number (p) and a page offset (d).
Physical address = Frame number * Page size + Offset
Paging removes external fragmentation but can cause internal fragmentation in the last page. A Translation Lookaside Buffer (TLB) is a small, fast associative cache of page-table entries that speeds up address translation.
Effective access time = Hit ratio * (TLB time + Memory time) + (1 - Hit ratio) * (TLB time + 2 * Memory time)

### Segmentation
Segmentation is a memory-management scheme that supports the user's view of memory, in which a program is a collection of variable-sized segments such as main function, stack, symbol table and arrays. A logical address is a pair (segment number, offset). The segment table stores a base and a limit for each segment; if the offset is greater than the limit, a trap is raised. Segmentation causes external fragmentation, which is why many systems combine segmentation with paging.

### Virtual memory
Virtual memory is a technique that allows the execution of processes that are not completely in main memory, so programs can be larger than physical memory. It is usually implemented with demand paging, in which a page is loaded into memory only when it is needed. When a process accesses a page that is not in memory, a page fault occurs: the OS finds a free frame, reads the page from disk, updates the page table and restarts the instruction.
Effective access time = (1 - p) * Memory access time + p * Page fault service time

### Page replacement algorithms
When there is no free frame on a page fault, a page replacement algorithm chooses a victim page to remove. FIFO page replacement removes the oldest page in memory; it suffers from Belady's anomaly, in which increasing the number of frames can increase the number of page faults. The Optimal page replacement algorithm replaces the page that will not be used for the longest time in the future; it gives the lowest page-fault rate but cannot be implemented because it needs future knowledge. LRU (Least Recently Used) replacement removes the page that has not been used for the longest time and is implemented with counters or a stack. LRU and Optimal do not suffer from Belady's anomaly.

### Thrashing
Thrashing is a situation in which a process spends more time paging (swapping pages in and out) than executing. It happens when a process does not have enough frames for its working set, so CPU utilisation drops sharply as the degree of multiprogramming increases. The working-set model prevents thrashing by giving each process enough frames for the set of pages it used in the most recent window of references. The page-fault frequency (PFF) approach sets upper and lower bounds on the page-fault rate and adds or removes frames accordingly.

--- page 6 ---

## Unit VI: File and Disk Management

### File allocation methods
There are three main file allocation methods. Contiguous allocation stores each file in a set of consecutive disk blocks; it supports fast sequential and direct access but causes external fragmentation and makes file growth difficult. Linked allocation stores a file as a linked list of disk blocks scattered anywhere on the disk; it has no external fragmentation but supports only sequential access, and a damaged pointer can lose the rest of the file. The File Allocation Table (FAT) is a variation of linked allocation. Indexed allocation brings all pointers of a file together into an index block, which supports direct access without external fragmentation; large files use linked, multilevel or combined (inode) index schemes.

### Disk scheduling algorithms
Disk scheduling decides the order in which pending disk I/O requests are served in order to minimise seek time.
Disk access time = Seek time + Rotational latency + Transfer time
FCFS disk scheduling serves requests in arrival order; it is fair but can cause long head movement. SSTF (Shortest Seek Time First) serves the request closest to the current head position, but it can starve far requests. SCAN, also called the elevator algorithm, moves the head from one end of the disk to the other, serving requests on the way, and then reverses. C-SCAN moves in one direction only and jumps back to the start, giving a more uniform waiting time. LOOK and C-LOOK are versions of SCAN and C-SCAN that go only as far as the last request in each direction.

### RAID
RAID (Redundant Array of Independent Disks) is a technique that combines multiple physical disks into one logical unit to improve performance, reliability, or both. RAID 0 uses striping without redundancy for speed. RAID 1 uses mirroring, keeping an exact copy of data on two disks. RAID 5 uses block-level striping with distributed parity, so it can survive the failure of one disk. RAID 6 adds a second parity block so it survives two disk failures. RAID 10 combines mirroring and striping for both speed and reliability.
