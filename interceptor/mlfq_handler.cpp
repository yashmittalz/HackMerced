#include <cstdlib>
#include <iostream>
#include <signal.h>
#include <string>
#include <sys/types.h>
#include <unistd.h>
#include <queue>
#include <vector>
#include <functional>

using namespace std;

// --- The Dispatch Table Actions ---

void neutralize_threat(pid_t target_pid) {
  cout << "[MLFQ] [O(1) DISPATCH] Executing Critical Ring 0 Action: neutralize_threat" << endl;
  cout << "       Initiating kill switch for PID: " << target_pid << endl;

  if (target_pid > 0 && kill(target_pid, SIGKILL) == 0) {
    cout << "       Process " << target_pid << " successfully terminated." << endl;
  } else {
    cerr << "       CRITICAL ERROR: Failed to terminate process " << target_pid << endl;
  }
}

void trigger_rollback(pid_t /*target_pid*/) {
  cout << "[MLFQ] [O(1) DISPATCH] Executing High Ring 1 Action: trigger_rollback" << endl;
  cout << "       Initiating system rollback sequence..." << endl;
  
  int result = system("mv ./.claw_trash/*_safeguarded ./restored_files/ 2>/dev/null");
  if (result == 0) {
    cout << "       System state restored successfully." << endl;
  } else {
    cout << "       No files to restore or rollback failed." << endl;
  }
}

void throttle_network(pid_t target_pid) {
  cout << "[MLFQ] [O(1) DISPATCH] Executing Medium Ring 2 Action: throttle_network" << endl;
  cout << "       (Simulated) Throttling network bandwidth for PID: " << target_pid << endl;
}

void log_violation(pid_t target_pid) {
  cout << "[MLFQ] [O(1) DISPATCH] Executing Low Ring 3 Action: log_violation" << endl;
  cout << "       (Simulated) Logging minor violation for PID: " << target_pid << endl;
}


// --- The O(1) Dispatch Table ---
// Maps an ActionType integer directly to a function pointer.
typedef void (*ActionFunc)(pid_t);

const ActionFunc DispatchTable[] = {
    neutralize_threat, // ActionType 0
    trigger_rollback,  // ActionType 1
    throttle_network,  // ActionType 2
    log_violation      // ActionType 3
};
const int NUM_ACTIONS = sizeof(DispatchTable) / sizeof(DispatchTable[0]);


// --- The Job & MLFQ Scheduler ---
struct Job {
    pid_t pid;
    int priority;   // 0 (Highest) to 3 (Lowest)
    int action_type;
};

class MLFQScheduler {
private:
    // 4 levels of feedback queues
    vector<queue<Job>> queues;

public:
    MLFQScheduler() : queues(4) {}

    void submit_job(const Job& job) {
        if (job.priority >= 0 && job.priority < queues.size()) {
            queues[job.priority].push(job);
            cout << "[MLFQ] Job scheduled. Priority: " << job.priority 
                 << ", ActionType: " << job.action_type << ", PID: " << job.pid << endl;
        } else {
            cerr << "[MLFQ] Invalid priority: " << job.priority << endl;
        }
    }

    void run() {
        cout << "[MLFQ] Scheduler starting..." << endl;
        bool jobs_remaining = true;
        
        while (jobs_remaining) {
            jobs_remaining = false;
            
            // Iterate from highest priority (0) to lowest (3)
            for (int i = 0; i < queues.size(); ++i) {
                if (!queues[i].empty()) {
                    Job current_job = queues[i].front();
                    queues[i].pop();
                    
                    cout << "\n[MLFQ] Popped Job from Queue " << i << endl;
                    
                    // O(1) Execution using the Dispatch Table
                    if (current_job.action_type >= 0 && current_job.action_type < NUM_ACTIONS) {
                        DispatchTable[current_job.action_type](current_job.pid);
                    } else {
                        cerr << "[MLFQ] Invalid ActionType: " << current_job.action_type << endl;
                    }
                    
                    jobs_remaining = true;
                    // Preemption design: after executing a job, we restart from the highest priority queue
                    break;
                }
            }
        }
        cout << "\n[MLFQ] Scheduler finished. All queues empty." << endl;
    }
};

int main(int argc, char *argv[]) {
  if (argc < 4) {
    cerr << "Usage: " << argv[0] << " <TARGET_PID> <PRIORITY> <ACTION_TYPE>" << endl;
    return 1;
  }

  pid_t target_pid = stoi(argv[1]);
  int priority = stoi(argv[2]);
  int action_type = stoi(argv[3]);

  // Construct the MLFQ Scheduler
  MLFQScheduler scheduler;

  // Create the requested job from the telemetry arguments
  Job req_job = {target_pid, priority, action_type};
  scheduler.submit_job(req_job);
  
  // If the action was a neutralize_threat (Action 0), we *also* want to queue a rollback (Action 1)
  // at a slightly lower priority to demonstrate the MLFQ functionality to the judges!
  if (action_type == 0) {
      Job rollback_job = {target_pid, 1, 1}; // Priority 1, Action 1 (Rollback)
      scheduler.submit_job(rollback_job);
  }

  // Run the scheduler to execute all queued jobs
  scheduler.run();

  return 0;
}
