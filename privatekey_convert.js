function hexToUint8Array(hexString) {
    // Remove '0x' prefix if present and any whitespace
    const hex = hexString.replace(/^0x/, '').replace(/\s/g, '');
    
    // Validate hex string
    if (hex.length === 0) {
        throw new Error('Empty hex string');
    }
    
    if (hex.length % 2 !== 0) {
        throw new Error('Invalid hex string length - must be even');
    }
    
    if (!/^[0-9a-fA-F]+$/.test(hex)) {
        throw new Error('Invalid hex string - contains non-hex characters');
    }
    
    const bytes = new Uint8Array(hex.length / 2);
    
    for (let i = 0; i < hex.length; i += 2) {
        bytes[i / 2] = parseInt(hex.substring(i, i + 2), 16);
    }
    
    return bytes;
}

// Example usage:
const privateKeyHex = "2zGo3B77Lxm4PEeQ3n8KrNk748TcrRXVHnqFz4kXrZUstuYguKDH6QrQPsiocQBzYnhyWY4KrHG68LKmAbwdrYPM"; // Replace with your actual key
const privateKeyArray = hexToUint8Array(privateKeyHex);

console.log('Original hex:', privateKeyHex);
console.log('Converted array:', privateKeyArray);
console.log('Array length:', privateKeyArray.length);

// Test with different formats
console.log('\nTesting different formats:');
console.log('With 0x prefix:', hexToUint8Array('0x1a2b3c'));
console.log('Without prefix:', hexToUint8Array('1a2b3c'));
console.log('Uppercase:', hexToUint8Array('1A2B3C'));