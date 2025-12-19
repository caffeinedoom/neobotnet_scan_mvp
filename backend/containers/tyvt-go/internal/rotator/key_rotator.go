package rotator

import (
	"sync"
	"time"
)

// KeyRotator manages rotation through multiple API keys
type KeyRotator struct {
	mu               sync.RWMutex
	keys             []string
	currentIndex     int
	rotationInterval time.Duration
	lastRotation     time.Time
	started          bool
	stopChan         chan struct{}
}

// NewKeyRotator creates a new key rotator with automatic rotation
func NewKeyRotator(keys []string, rotationInterval time.Duration) *KeyRotator {
	kr := &KeyRotator{
		keys:             keys,
		currentIndex:     0,
		rotationInterval: rotationInterval,
		lastRotation:     time.Now(),
		stopChan:         make(chan struct{}),
	}

	// Only start auto-rotation if we have multiple keys
	if len(keys) > 1 {
		go kr.autoRotate()
	}

	return kr
}

// CurrentKey returns the currently active API key
func (kr *KeyRotator) CurrentKey() string {
	kr.mu.RLock()
	defer kr.mu.RUnlock()

	if len(kr.keys) == 0 {
		return ""
	}

	return kr.keys[kr.currentIndex]
}

// RotateKey manually rotates to the next key and returns it
func (kr *KeyRotator) RotateKey() string {
	kr.mu.Lock()
	defer kr.mu.Unlock()

	if len(kr.keys) <= 1 {
		if len(kr.keys) == 1 {
			return kr.keys[0]
		}
		return ""
	}

	kr.currentIndex = (kr.currentIndex + 1) % len(kr.keys)
	kr.lastRotation = time.Now()

	return kr.keys[kr.currentIndex]
}

// GetKeyCount returns the number of configured keys
func (kr *KeyRotator) GetKeyCount() int {
	kr.mu.RLock()
	defer kr.mu.RUnlock()
	return len(kr.keys)
}

// GetCurrentIndex returns the current key index (for logging)
func (kr *KeyRotator) GetCurrentIndex() int {
	kr.mu.RLock()
	defer kr.mu.RUnlock()
	return kr.currentIndex
}

// Stop stops the auto-rotation goroutine
func (kr *KeyRotator) Stop() {
	kr.mu.Lock()
	defer kr.mu.Unlock()

	if kr.started {
		close(kr.stopChan)
		kr.started = false
	}
}

// autoRotate runs in a goroutine and rotates keys on the configured interval
func (kr *KeyRotator) autoRotate() {
	kr.mu.Lock()
	kr.started = true
	kr.mu.Unlock()

	ticker := time.NewTicker(kr.rotationInterval)
	defer ticker.Stop()

	for {
		select {
		case <-ticker.C:
			kr.RotateKey()
		case <-kr.stopChan:
			return
		}
	}
}

