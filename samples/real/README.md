# Real sample logs

These are redacted excerpts from a real `nvidia-bug-report.log` (user-provided upload).
Hostname replaced with `gpu-node-01`. GPU serial/UUID left as-is (already anonymous/non-identifying).

## incident1_first_occurrence.log
First occurrence of Xid 79 ("GPU has fallen off the bus") followed by Xid 154
(GPU recovery action changed to "Reset Required"). Includes surrounding GSP RPC
history context. Repeated `_issueRpcAndWait` failure lines trimmed for readability
(originally ~1786 sequence numbers deep — note this pattern, it's common and your
parser should collapse/count repeats rather than treat each as distinct).

## incident2_recurrence.log
Same Xid 79 -> 154 pattern recurring ~11 hours later on the same GPU (same PCI
address, same GPU UUID/serial). This recurrence is the key signal: NVIDIA's own
guidance treats a *repeated* Xid 79 as escalation-worthy (possible hardware fault,
not a one-off transient condition) rather than routine.

Source: user-provided nvidia-bug-report.log, timestamps Feb 2026.
