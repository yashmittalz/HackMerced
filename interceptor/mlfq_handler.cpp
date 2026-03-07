#include <cstdlib>
#include <iostream>
#include <signal.h>
#include <string>
#include <sys/types.h>

using namespace std;

// This binary will act as the executable triggered by the Python Webhook
// Listener when Splunk detects a critical anomaly.

void neutralize_threat(pid_t target_pid) {
  cout << "[MLFQ HANDLER] Initiating kill switch for PID: " << target_pid
       << endl;

  // Applying kill -9 guarantees process termination at the OS kernel level
  // before the AI agent can execute further instructions.
  if (kill(target_pid, SIGKILL) == 0) {
    cout << "[MLFQ HANDLER] Process " << target_pid
         << " successfully terminated." << endl;
  } else {
    cerr << "[MLFQ HANDLER] CRITICAL ERROR: Failed to terminate process "
         << target_pid << endl;
  }
}

void trigger_rollback() {
  cout << "[MLFQ HANDLER] Initiating system rollback sequence..." << endl;
  // Shelling out here for simplicity in the boilerplate,
  // but a prod version would iterate over the .claw_trash directory using
  // <filesystem>.
  int result =
      system("mv ./.claw_trash/*_safeguarded ./restored_files/ 2>/dev/null");
  if (result == 0) {
    cout << "[MLFQ HANDLER] System state restored successfully." << endl;
  }
}

int main(int argc, char *argv[]) {
  if (argc < 2) {
    cerr << "Usage: " << argv[0] << " <TARGET_PID>" << endl;
    return 1;
  }

  pid_t target_pid = stoi(argv[1]);

  // Dispatching immediate kill order
  neutralize_threat(target_pid);

  // Rollback changes saved by the LD_PRELOAD hook
  trigger_rollback();

  return 0;
}
