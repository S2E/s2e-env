update_guest_tools

# Don't print crashes in the syslog. This prevents unnecessary forking in the
# kernel
sudo sysctl -w debug.exception-trace=0

# Prevent core dumps from being created. This prevents unnecessary forking in
# the kernel
ulimit -c 0

# Ensure that /tmp is mounted in memory (if you built the image using s2e-env
# then this should already be the case. But better to be safe than sorry!)
if ! mount | grep "/tmp type tmpfs"; then
    sudo mount -t tmpfs -osize=10m tmpfs /tmp
fi

# Download the target file to analyze
./s2eget "{{ target }}"

# Run the analysis
execute "./{{ target }}"

# Kill states before exiting
./s2ecmd kill 0 "'{{ target }}' state killed"
