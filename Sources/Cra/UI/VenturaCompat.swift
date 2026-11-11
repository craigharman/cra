import AppKit
import QuartzCore
import SwiftUI

/// Once-a-frame callbacks: a CADisplayLink on macOS 14 and later, a 60 Hz timer on Ventura,
/// which has no CADisplayLink. Callers read the same three members from either.
@objc protocol FrameTicker: NSObjectProtocol {
    var timestamp: CFTimeInterval { get }
    var targetTimestamp: CFTimeInterval { get }
    func invalidate()
}

@available(macOS 14.0, *)
extension CADisplayLink: FrameTicker {}

/// Ventura's stand-in for CADisplayLink. Like a display link it keeps its target until
/// invalidated; the frame it reports is the moment it fired, the next one 1/60 s later.
private final class TimerTicker: NSObject, FrameTicker {
    private static let interval = 1.0 / 60
    private var timer: Timer?
    private(set) var timestamp = CACurrentMediaTime()
    var targetTimestamp: CFTimeInterval { timestamp + Self.interval }

    init(target: NSObject, selector: Selector) {
        super.init()
        let timer = Timer(timeInterval: Self.interval, repeats: true) { [unowned self] _ in
            timestamp = CACurrentMediaTime()
            _ = target.perform(selector, with: self)
        }
        RunLoop.main.add(timer, forMode: .common)
        self.timer = timer
    }

    func invalidate() {
        timer?.invalidate()
        timer = nil
    }
}

extension NSView {
    /// Calls `selector` on `target` (with the ticker) every frame of this view's display, in
    /// the common run loop modes, until the ticker is invalidated.
    func startFrameTicker(target: NSObject, selector: Selector) -> any FrameTicker {
        if #available(macOS 14.0, *) {
            let link = displayLink(target: target, selector: selector)
            link.add(to: .main, forMode: .common)
            return link
        }
        return TimerTicker(target: target, selector: selector)
    }
}

extension CASpringAnimation {
    /// `init(perceptualDuration:bounce:)` on macOS 14 and later. On Ventura, the same spring
    /// from mass 1, stiffness (2π/duration)² and damping 4π(1 − bounce)/duration (bounce ≥ 0).
    static func perceptual(duration: Double, bounce: Double) -> CASpringAnimation {
        if #available(macOS 14.0, *) {
            return CASpringAnimation(perceptualDuration: duration, bounce: bounce)
        }
        let spring = CASpringAnimation()
        spring.mass = 1
        spring.stiffness = pow(2 * .pi / duration, 2)
        spring.damping = 4 * .pi * (1 - bounce) / duration
        return spring
    }
}

extension View {
    /// `.buttonBorderShape(.roundedRectangle(radius:))` on macOS 14 and later; Ventura has only
    /// the system's own corner radius.
    @ViewBuilder func roundedButtonBorder(radius: CGFloat) -> some View {
        if #available(macOS 14.0, *) {
            buttonBorderShape(.roundedRectangle(radius: radius))
        } else {
            buttonBorderShape(.roundedRectangle)
        }
    }
}
