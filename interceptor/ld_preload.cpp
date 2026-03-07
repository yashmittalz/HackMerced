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
#include <unistd.h>

// Typedefs for the original system calls we are hooking
typedef int (*orig_unlink_t)(const char *pathname);
typedef int (*orig_remove_t)(const char *pathname);
typedef int (*orig_open_t)(const char *pathname, int flags, ...);

// Teleports files to the quarantine folder instead of deleting them.
// Operates in O(1) time complexity (if on the same filesystem).
int isolate_file(const char *pathname) {
  char quarantine_path[1024];
  // .claw_trash should ideally be created at initialization or startup.
  snprintf(quarantine_path, sizeof(quarantine_path),
           "./.claw_trash/%s_safeguarded", pathname);
  return rename(pathname, quarantine_path);
}

// Hooking the 'unlink' system call
int unlink(const char *pathname) {
  orig_unlink_t orig_unlink;
  orig_unlink = (orig_unlink_t)dlsym(RTLD_NEXT, "unlink");

  printf("[SECURITY FIREWALL] Intercepted unlink attempt on: %s\n", pathname);

  // Instead of actually unlinking, we isolate the file via O(1) rename
  if (isolate_file(pathname) == 0) {
    printf("[SECURITY FIREWALL] Successfully teleported %s to quarantine.\n",
           pathname);
    return 0; // Fake success back to the calling process
  }

  // If isolation failed, we aggressively deny the deletion altogether
  printf("[SECURITY FIREWALL] BLOCKING irreversible deletion of %s.\n",
         pathname);
  return -1;
}

// Hooking the 'remove' system call
int remove(const char *pathname) {
  orig_remove_t orig_remove;
  orig_remove = (orig_remove_t)dlsym(RTLD_NEXT, "remove");

  printf("[SECURITY FIREWALL] Intercepted remove attempt on: %s\n", pathname);

  if (isolate_file(pathname) == 0) {
    printf("[SECURITY FIREWALL] Successfully teleported %s to quarantine.\n",
           pathname);
    return 0;
  }

  printf("[SECURITY FIREWALL] BLOCKING irreversible deletion of %s.\n",
         pathname);
  return -1;
}

// Hooking the 'open' system call to protect peripherals
int open(const char *pathname, int flags, ...) {
  orig_open_t orig_open;
  orig_open = (orig_open_t)dlsym(RTLD_NEXT, "open");

  // Block access to the Webcam
  if (strcmp(pathname, "/dev/video0") == 0) {
    printf("[SECURITY FIREWALL] Unauthorized camera access blocked! Path: %s\n",
           pathname);
    return -1; // Deny access
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
