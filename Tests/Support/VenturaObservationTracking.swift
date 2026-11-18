import Perception

// Fork only (docs/ventura-port.md): upstream's tests call Observation's withObservationTracking,
// which needs macOS 14. The harnesses build for macOS 13, where the app's models are
// @Perceptible, so the same call goes to Perception and the test bodies (and their
// Tests/promises.lock hashes) stay as upstream wrote them. scripts/ventura-perceptify.py adds
// this file to any harness whose tests call it.
@discardableResult
func withObservationTracking<Value>(_ read: () -> Value, onChange: @escaping @Sendable () -> Void) -> Value {
    withPerceptionTracking(read, onChange: onChange)
}
