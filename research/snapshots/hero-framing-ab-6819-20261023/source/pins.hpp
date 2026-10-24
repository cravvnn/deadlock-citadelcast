#pragma once
#include <array>
#include <cstdint>
constexpr char kServerHash[] = "4855ef0712962f43aa4d9f623b258ada286d3e6f8fd2a2c8272984bfecf777e8";
constexpr char kTierHash[] = "666c9022739190d571a67161646d1a55511e130b62c3a93f8c95b47beaede433";
constexpr std::uintptr_t kCvarTable = 0x313208;
constexpr std::array<std::uintptr_t, 46> kCvarSlots = {0x789e0,0x789d0,0x695a0,0x68f40,0x69090,0x86a0,0x652a0,0x652a0,0x78a00,0x8690,0x65a50,0x6c6b0,0x6c8c0,0x6ca00,0x6af30,0x6b120,0x6b290,0x6cb10,0x6cd00,0x6ce20,0x6d030,0x6d5c0,0x6d790,0x6d880,0x6d9e0,0x72ac0,0x6db50,0x6dde0,0x72b60,0x72e80,0x73130,0x73440,0x77d70,0x77d80,0x780d0,0x6ded0,0x6dee0,0x6e050,0x6b740,0x6c2f0,0x6c0f0,0x6c5f0,0x69ff0,0x6a4f0,0x6cf20,0x6b460};
constexpr std::uintptr_t kConfigTable = 0x2b5a1b0;
constexpr std::uintptr_t kConfigConnect = 0x99d9e4;
constexpr std::uintptr_t kConfigDisconnect = 0x99d9f0;
constexpr std::uintptr_t kConfigInterval = 0x99ab40;

// Named camera/consumer proof: adapter-disk-review.json and manager-methods.json.
constexpr char kClientHash[] = "c09143cf9cd722909404c64e3ffa05157afc15e8a3519b49a1396a627af8ca85";
constexpr char kEngineHash[] = "f7dd5763050e203361809360b4354ef3f768753bb6e43fb314d4822065d28da6";
constexpr char kWalkerCarrierHash[] = "f059f0df190f082fff729acabb07d6eae20c8043b8ff04d895e09f052e33f189";
constexpr std::uintptr_t kManagerTable = 0x277d030;
constexpr std::uintptr_t kDataTable = 0x2c36160;
constexpr std::uintptr_t kFullyConnected = 0x730f0;
constexpr std::uintptr_t kGetManager = 0x5c35c0;
constexpr std::uintptr_t kCameraFactory = 0x1939330;
constexpr std::uintptr_t kDataCameraType = 0x343eae0;
constexpr std::uintptr_t kDataSetup = 0x1943f40;
constexpr std::uintptr_t kDataLoad = 0x1aa8eb0;
// native-target-phase-disk-review.json: dirty world-transform cache is refreshed
// before returning the selected entity's absolute-origin field.
constexpr std::uintptr_t kHeroAbsoluteOriginGetter = 0xa7bbc0;
// New narrow network-module review: cached label used by engine status only.
constexpr char kNetworkHash[] = "5483a9b5a02a16d98431b89b8f2604f5511d37ddd4a396a608ced1d7ce946eef";
constexpr std::uintptr_t kNetworkClientGlobal = 0x8b2dc0;
constexpr std::uintptr_t kChannelTable = 0x237c28;
constexpr std::uintptr_t kChannelStatusLabel = 0xbdfb0;

struct CameraSlotPin { unsigned slot; std::uintptr_t method; };
constexpr CameraSlotPin kManagerSlotPins[] = {
    {0, 0x5b8a50},
    {2, 0x5d9b90},
    {8, 0x1943470},
    {9, 0x1953f20},
    {10, 0x193a950},
    {11, 0x193a960},
    {16, 0x1947440},
    {17, 0x1947460},
};
constexpr CameraSlotPin kDataSlotPins[] = {
    {0, 0x1aa6d40},
    {1, 0x1943f40},
    {2, 0x194c5c0},
    {3, 0x1aaa620},
    {4, 0x194c4f0},
    {6, 0x1aa9b10},
    {7, 0x5d0d40},
    {12, 0x5c63d0},
    {15, 0x5c4580},
    {17, 0x1942200},
    {18, 0x19422b0},
    {52, 0x1943460},
};

// Measured Watch observer and retained native-default types; ownership proof is
// observer-ownership-disk-review.json, correlated with the owned diagnostic.
constexpr std::uintptr_t kObserverTable=0x2784a98;
constexpr std::uintptr_t kRetainedTable=0x277c788;
constexpr CameraSlotPin kObserverSlotPins[]={{0,0x5eaa00},{6,0x5d0d30},{7,0x5d0d40},
    {3,0x614db0},{12,0x5fe830},{15,0x5fc900},{17,0x1942200}};
