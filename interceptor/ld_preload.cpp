#ifndef _GNU_SOURCE
#define _GNU_SOURCE
#endif
#include <dlfcn.h>
#include <fcntl.h>
#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <sys/wait.h>
#include <unistd.h>

// Firebase REST endpoint for live telemetry stream on the dashboard
#define FIREBASE_TELEMETRY_URL \
  "https://openclaw-sentinal-default-rtdb.firebaseio.com/telemetry.json"

// Runs exactly once when the shared library is loaded via LD_PRELOAD
__attribute__((constructor))
static void firewall_init() {
  mkdir(".claw_trash", 0755);
  mkdir("./restored_files", 0755);
  printf("[SECURITY FIREWALL] OS Interceptor loaded. Quarantine directory ready.\n");
}

// Fire-and-forget push to Firebase (non-blocking via fork+exec)
static void push_telemetry_to_firebase(const char *message) {
  pid_t pid = fork();
  if (pid == 0) {
    // Child process: use curl to POST the event to Firebase
    char payload[2048];
    snprintf(payload, sizeof(payload),
             "{\"message\": \"%s\", \"source\": \"ld_preload\"}",
             message);
    execlp("curl", "curl", "-s", "-X", "POST",
           FIREBASE_TELEMETRY_URL,
           "-H", "Content-Type: application/json",
           "-d", payload, NULL);
    _exit(0); // Only reached if execlp fails
  } else if (pid > 0) {
    // Parent: don't wait — we need to be non-blocking (O(1) intercept stays fast)
    signal(SIGCHLD, SIG_IGN); // Prevent zombie processes
  }
}

typedef int (*orig_unlink_t)(const char *pathname);
typedef int (*orig_remove_t)(const char *pathname);
typedef int (*orig_open_t)(const char *pathname, int flags, ...);

// Teleports files to the quarantine folder instead of deleting them.
// Operates in O(1) time complexity (if on the same filesystem).
int isolate_file(const char *pathname) {
  char quarantine_path[1024];
  // .claw_trash should ideally be created at initialization or startup.
  const char *base = strrchr(pathname, '/');
  if (!base)
    base = pathname;
  else
    base++;
  snprintf(quarantine_path, sizeof(quarantine_path),
           "/workspace/.claw_trash/%s_safeguarded", base);
  // Try renaming first (O(1) time), but Docker volumes fail cross-device
  // renames.
  if (rename(pathname, quarantine_path) == 0) {
    return 0;
  }

  // Fallback: Copy the file byte-by-byte into the quarantine volume
  int src_fd = open(pathname, O_RDONLY);
  if (src_fd < 0)
    return -1;
  // Ensure quarantine directory exists before creating destination file
  mkdir("/workspace/.claw_trash", 0755);
  int dest_fd = open(quarantine_path, O_WRONLY | O_CREAT | O_TRUNC, 0644);
  if (dest_fd < 0) {
    close(src_fd);
    return -1;
  }

  char buf[4096];
  ssize_t bytes_read;
  while ((bytes_read = read(src_fd, buf, sizeof(buf))) > 0) {
    write(dest_fd, buf, bytes_read);
  }

  close(src_fd);
  close(dest_fd);

  // Ensure .claw_trash directory exists (ignore errors if it already does)
  mkdir("/workspace/.claw_trash", 0755);

  // Create a placeholder empty file at the original location so libuv stats
  // succeed
  int placeholder_fd = open(pathname, O_CREAT | O_WRONLY | O_TRUNC, 0644);
  if (placeholder_fd >= 0)
    close(placeholder_fd);

  return 0;
} // Hooking the 'unlink' system call
int unlink(const char *pathname) {
  orig_unlink_t orig_unlink = (orig_unlink_t)dlsym(RTLD_NEXT, "unlink");

  // Explicitly allow OpenClaw's internal Node.js lock and socket files to be
  // deleted
  if (strstr(pathname, ".lock") != NULL || strstr(pathname, ".sock") != NULL) {
    return orig_unlink(pathname);
  }

  printf("[SECURITY FIREWALL] Intercepted unlink attempt on: %s\n", pathname);

  if (isolate_file(pathname) == 0) {
    char msg[512];
    snprintf(msg, sizeof(msg), "[INTERCEPTED] unlink('%s') redirected to quarantine", pathname);
    push_telemetry_to_firebase(msg);
    printf("[SECURITY FIREWALL] Successfully teleported %s to quarantine.\n", pathname);
    return 0;
  }

  char msg[512];
  snprintf(msg, sizeof(msg), "[BLOCKED] unlink('%s') hard-denied", pathname);
  push_telemetry_to_firebase(msg);
  printf("[SECURITY FIREWALL] BLOCKING irreversible deletion of %s.\n", pathname);
  return -1;
}

// Hooking the 'remove' system call
int remove(const char *pathname) {
  orig_remove_t orig_remove = (orig_remove_t)dlsym(RTLD_NEXT, "remove");

  // Explicitly allow OpenClaw's internal Node.js lock and socket files to be
  // deleted
  if (strstr(pathname, ".lock") != NULL || strstr(pathname, ".sock") != NULL) {
    return orig_remove(pathname);
  }

  printf("[SECURITY FIREWALL] Intercepted remove attempt on: %s\n", pathname);

  if (isolate_file(pathname) == 0) {
    char msg[512];
    snprintf(msg, sizeof(msg), "[INTERCEPTED] remove('%s') redirected to quarantine", pathname);
    push_telemetry_to_firebase(msg);
    printf("[SECURITY FIREWALL] Successfully teleported %s to quarantine.\n", pathname);
    return 0;
  }

  char msg[512];
  snprintf(msg, sizeof(msg), "[BLOCKED] remove('%s') hard-denied", pathname);
  push_telemetry_to_firebase(msg);
  printf("[SECURITY FIREWALL] BLOCKING irreversible deletion of %s.\n", pathname);
  return -1;
}

// Hooking the 'open' system call to protect peripherals
int open(const char *pathname, int flags, ...) {
  orig_open_t orig_open;
  orig_open = (orig_open_t)dlsym(RTLD_NEXT, "open");

  // Block access to the Webcam
  if (strcmp(pathname, "/dev/video0") == 0) {
    push_telemetry_to_firebase("[HARDWARE BREACH] Unauthorized camera access blocked: /dev/video0");
    printf("[SECURITY FIREWALL] Unauthorized camera access blocked! Path: %s\n", pathname);
    return -1;
  }

  // Default behavior for all other files
  mode_t mode = 0;
  if (flags & O_CREAT) {
    va_list args;
    va_start(args, flags);
    mode = va_arg(args, int); // mode_t is promoted to int
    va_end(args);
    return orig_open(pathname, flags, mode);
  }

  return orig_open(pathname, flags);
}
