
import os

def clean_env_file():
    env_path = '.env'
    if not os.path.exists(env_path):
        print(f"{env_path} not found.")
        return

    print(f"Reading {env_path}...")
    with open(env_path, 'rb') as f:
        content = f.read()

    original_len = len(content)
    # Remove null bytes (0x00) and BOM (if any)
    cleaned_content = content.replace(b'\x00', b'')
    
    # Also handle potential UTF-16 BOM if strictly UTF-16
    if cleaned_content.startswith(b'\xff\xfe'):
        cleaned_content = cleaned_content[2:]
    
    # Decode to string (attempt utf-8, ignore errors)
    try:
        text_content = cleaned_content.decode('utf-8')
    except UnicodeDecodeError:
        print("UTF-8 decode failed, trying manual byte cleanup...")
        text_content = cleaned_content.decode('latin-1') # Fallback

    # Remove duplicates if any logic appended incorrectly
    lines = text_content.splitlines()
    unique_lines = []
    seen_keys = set()
    
    final_lines = []
    
    for line in lines:
        line = line.strip()
        if not line: 
            continue
        if line.startswith('#'):
            final_lines.append(line)
            continue
            
        if '=' in line:
            key = line.split('=')[0].strip()
            # If we see the same key later, usually the later one overrides.
            # But here we just want to clean up mess. Let's keep all and let python-dotenv handle override?
            # Actually deduplication is better to strictly clean file.
            # Let's just create a list and if dupes exist, take the last one? 
            # Simplified: Just write back non-null lines.
            final_lines.append(line)
    
    print(f"Original size: {original_len} bytes")
    print(f"Cleaned lines: {len(final_lines)}")
    
    with open(env_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(final_lines) + '\n')
        
    print(f"Successfully cleaned {env_path}")

if __name__ == "__main__":
    clean_env_file()
