// swift-tools-version:5.10
import PackageDescription

// Cra's decisions that need no window and no Chromium: models, Arc import mapping, layout
// arithmetic. A package of its own so `swift test --package-path Packages/CraCore` builds
// and runs without vendor/cef (a target in the root package would build CEF first).
let package = Package(
    name: "CraCore",
    platforms: [.macOS(.v13)],
    products: [
        .library(name: "CraCore", targets: ["CraCore"]),
        // Direct swiftc test harnesses need a linkable archive of Perception.
        .library(name: "CraPerceptionTestSupport", type: .static, targets: ["CraPerceptionTestSupport"]),
    ],
    dependencies: [
        .package(url: "https://github.com/pointfreeco/swift-perception", exact: "2.0.12"),
    ],
    targets: [
        .target(name: "CraPerceptionTestSupport", dependencies: [.product(name: "Perception", package: "swift-perception")]),
        .target(name: "CraCore", dependencies: [.product(name: "Perception", package: "swift-perception")]),
        .testTarget(name: "CraCoreTests", dependencies: ["CraCore", .product(name: "Perception", package: "swift-perception")], resources: [.copy("Fixtures")]),
    ],
    swiftLanguageVersions: [.v5]
)
