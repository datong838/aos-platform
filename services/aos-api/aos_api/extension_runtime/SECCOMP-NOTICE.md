# Seccomp baseline attribution

Derived from Moby profiles `seccomp/default.json`, Git blob
`ea5a494afb8d64898fa0f4f47ae0c4f5ba9cbbc9`, Apache-2.0 (MOBY-LICENSE).
Source: https://github.com/moby/profiles

AOS modification (2026-09-05): remove all allowances for mount, umount,
umount2, fsopen, fsconfig, fsmount, fspick, move_mount, mount_setattr,
open_tree, ptrace, process_vm_readv, process_vm_writev, mknod, mknodat,
iopl and ioperm. Preserve default deny and all remaining restrictions.
This is a pinned policy; no runtime download or permissive fallback.
