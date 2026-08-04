import socket
import subprocess
import platform

def is_port_in_use(port):
    """Check if a port is in use on either IPv4 or IPv6."""
    # Check IPv4
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        ipv4_in_use = s.connect_ex(('127.0.0.1', port)) == 0
    
    # Check IPv6
    ipv6_in_use = False
    try:
        with socket.socket(socket.AF_INET6, socket.SOCK_STREAM) as s:
            ipv6_in_use = s.connect_ex(('::1', port)) == 0
    except socket.error:
        # IPv6 might not be supported
        pass
    
    return ipv4_in_use or ipv6_in_use

def free_port(port):
    """Attempt to free a port by killing the process using it."""
    try:
        if platform.system() == "Windows":
            # Find the process ID using the port (both IPv4 and IPv6)
            result = subprocess.run(
                f'netstat -ano | findstr :{port}', 
                shell=True, 
                capture_output=True, 
                text=True
            )
            
            if result.stdout:
                # Extract the PID from the last column
                pids = set()
                for line in result.stdout.strip().split('\n'):
                    if "LISTENING" in line:
                        parts = line.strip().split()
                        if len(parts) > 4:
                            pid = parts[-1]
                            pids.add(pid)
                
                if pids:
                    for pid in pids:
                        print(f"Found process using port {port}: PID {pid}")
                        # Kill the process
                        subprocess.run(f'taskkill /F /PID {pid}', shell=True)
                    return True
            return False
        elif platform.system() == "Linux" or platform.system() == "Darwin":  # Linux or macOS
            cmd = f"lsof -i :{port} | grep LISTEN | awk '{{print $2}}'"
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
            
            if result.stdout:
                for pid in result.stdout.strip().split('\n'):
                    if pid:
                        print(f"Found process using port {port}: PID {pid}")
                        subprocess.run(f'kill -9 {pid}', shell=True)
                return True
            return False
        else:
            print(f"Unsupported operating system: {platform.system()}")
            return False
    except Exception as e:
        print(f"Error freeing port: {e}")
        return False 