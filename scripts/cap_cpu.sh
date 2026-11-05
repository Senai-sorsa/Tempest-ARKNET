# Source this before launching a job from Git Bash: pins THIS shell (and so everything it starts) to 12 logical CPUs at
# BelowNormal priority. The user's cap is 12 of 20 (mask 4095); there is no background limiter loop any more.
_winpid=$(cat /proc/$$/winpid 2>/dev/null)
[ -n "$_winpid" ] && powershell -NoProfile -c "\$p = Get-Process -Id $_winpid; \$p.ProcessorAffinity = [IntPtr]4095; \$p.PriorityClass = 'BelowNormal'" >/dev/null 2>&1
export OMP_NUM_THREADS=12
