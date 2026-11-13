# Source this before launching a job from Git Bash: pins THIS shell (and so everything it starts) to 18 logical CPUs at
# BelowNormal priority. The user's cap is 18 of 20 (mask 262143; raised from 12 by the user 2026-11-13); there is no background limiter loop any more.
_winpid=$(cat /proc/$$/winpid 2>/dev/null)
[ -n "$_winpid" ] && powershell -NoProfile -c "\$p = Get-Process -Id $_winpid; \$p.ProcessorAffinity = [IntPtr]262143; \$p.PriorityClass = 'BelowNormal'" >/dev/null 2>&1
export OMP_NUM_THREADS=18
