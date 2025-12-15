package config

import (
	"fmt"
	"log"
	"os"
	"strings"
	"time"
)

// LogLevel represents logging severity
type LogLevel int

const (
	DEBUG LogLevel = iota
	INFO
	WARN
	ERROR
)

// String returns the string representation of log level
func (l LogLevel) String() string {
	switch l {
	case DEBUG:
		return "DEBUG"
	case INFO:
		return "INFO"
	case WARN:
		return "WARN"
	case ERROR:
		return "ERROR"
	default:
		return "UNKNOWN"
	}
}

// Logger provides structured logging with context
type Logger struct {
	level      LogLevel
	context    map[string]string
	logger     *log.Logger
	useColors  bool
	startTime  time.Time
}

// Color codes for terminal output (optional)
const (
	colorReset  = "\033[0m"
	colorRed    = "\033[31m"
	colorYellow = "\033[33m"
	colorBlue   = "\033[34m"
	colorGray   = "\033[37m"
)

// NewLogger creates a new structured logger
func NewLogger(context map[string]string) *Logger {
	// Parse log level from environment (default: INFO)
	levelStr := strings.ToUpper(os.Getenv("LOG_LEVEL"))
	level := INFO
	switch levelStr {
	case "DEBUG":
		level = DEBUG
	case "INFO":
		level = INFO
	case "WARN":
		level = WARN
	case "ERROR":
		level = ERROR
	}

	// Disable colors in production (ECS environment)
	useColors := os.Getenv("ENV") != "production"

	return &Logger{
		level:     level,
		context:   context,
		logger:    log.New(os.Stdout, "", 0), // No prefix, we'll format ourselves
		useColors: useColors,
		startTime: time.Now(),
	}
}

// log formats and writes a log message with context
func (l *Logger) log(level LogLevel, format string, args ...interface{}) {
	// Skip if below configured level
	if level < l.level {
		return
	}

	// Build message
	message := fmt.Sprintf(format, args...)

	// Format timestamp
	timestamp := time.Now().Format("2006-01-02 15:04:05.000")

	// Build context string
	contextStr := ""
	for key, value := range l.context {
		if contextStr != "" {
			contextStr += " "
		}
		contextStr += fmt.Sprintf("%s=%s", key, value)
	}

	// Add color based on level (if enabled)
	color := colorReset
	emoji := ""
	if l.useColors {
		switch level {
		case DEBUG:
			color = colorGray
			emoji = "🔍 "
		case INFO:
			color = colorBlue
			emoji = "ℹ️  "
		case WARN:
			color = colorYellow
			emoji = "⚠️  "
		case ERROR:
			color = colorRed
			emoji = "❌ "
		}
	}

	// Format: [TIMESTAMP] LEVEL [CONTEXT] emoji MESSAGE
	logLine := fmt.Sprintf("%s[%s] %-5s", color, timestamp, level)
	if contextStr != "" {
		logLine += fmt.Sprintf(" [%s]", contextStr)
	}
	logLine += fmt.Sprintf(" %s%s%s", emoji, message, colorReset)

	l.logger.Println(logLine)
}

// Debug logs a debug message (verbose, development only)
func (l *Logger) Debug(format string, args ...interface{}) {
	l.log(DEBUG, format, args...)
}

// Info logs an informational message (normal operations)
func (l *Logger) Info(format string, args ...interface{}) {
	l.log(INFO, format, args...)
}

// Warn logs a warning message (recoverable issues)
func (l *Logger) Warn(format string, args ...interface{}) {
	l.log(WARN, format, args...)
}

// Error logs an error message (critical failures)
func (l *Logger) Error(format string, args ...interface{}) {
	l.log(ERROR, format, args...)
}

// WithField adds a context field to the logger (returns new logger)
func (l *Logger) WithField(key, value string) *Logger {
	newContext := make(map[string]string)
	for k, v := range l.context {
		newContext[k] = v
	}
	newContext[key] = value

	return &Logger{
		level:     l.level,
		context:   newContext,
		logger:    l.logger,
		useColors: l.useColors,
		startTime: l.startTime,
	}
}

// LogStats logs performance statistics
func (l *Logger) LogStats(stats map[string]interface{}) {
	statsStr := ""
	for key, value := range stats {
		if statsStr != "" {
			statsStr += ", "
		}
		statsStr += fmt.Sprintf("%s=%v", key, value)
	}
	l.Info("Performance Stats: %s", statsStr)
}

// LogDuration logs the elapsed time since logger creation
func (l *Logger) LogDuration(operation string) {
	duration := time.Since(l.startTime)
	l.Info("%s completed in %v", operation, duration)
}

// LogProgress logs progress with percentage
func (l *Logger) LogProgress(current, total int, operation string) {
	percentage := 0.0
	if total > 0 {
		percentage = (float64(current) / float64(total)) * 100
	}
	l.Info("%s: %d/%d (%.1f%%)", operation, current, total, percentage)
}

