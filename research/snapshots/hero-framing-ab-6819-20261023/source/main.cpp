// Independent test variant of Artemon121/cvar-unhide-s2-citadel v0.5.3 (MIT).
// Original sources/license and SHA-256 provenance are retained alongside this build.
#include "appframework/IAppSystem.h"
#include "icommandline.h"
#include "interface.h"
#include "interfaces/interfaces.h"
#include "icvar.h"
#include <windows.h>
#include <bcrypt.h>
#include <array>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <string>
#include <vector>
#include "pins.hpp"
#include "lifecycle.hpp"
#include "hooks.hpp"
#include "adapter.hpp"

static_assert(sizeof(ConVarRef) == 8 && sizeof(ConCommandRef) == 8);
static_assert(sizeof(CCommand) == 0x650);
static_assert(offsetof(ConCommandCreation_t, m_pszName) == 0);
static_assert(offsetof(ConCommandCreation_t, m_pszHelpString) == 8);
static_assert(offsetof(ConCommandCreation_t, m_nFlags) == 0x10);
static_assert(offsetof(ConCommandCreation_t, m_CBInfo) == 0x18);
static_assert(offsetof(ConCommandCreation_t, m_CompletionCBInfo) == 0x28);
static_assert(offsetof(ConCommandData, m_nFlags) == 0x10);

void UnregisterUnlockerCommands();
extern ICvar* cvar;
static INIT_ONCE once = INIT_ONCE_STATIC_INIT;
static SRWLOCK hook_lock = SRWLOCK_INIT;
static SRWLOCK registration_lock = SRWLOCK_INIT;
static CreateInterfaceFn real_factory{};
static HMODULE real_module{};
static void* original_connect{};
static void* original_disconnect{};
static IAppSystem* hooked_config{};
static OwnedRegistration registration;

std::string CitadelCastHashFile(const char* path) {
    HANDLE file = CreateFileA(path, GENERIC_READ, FILE_SHARE_READ | FILE_SHARE_DELETE,
                              nullptr, OPEN_EXISTING, FILE_FLAG_SEQUENTIAL_SCAN, nullptr);
    if (file == INVALID_HANDLE_VALUE) return {};
    BCRYPT_ALG_HANDLE algorithm{}; BCRYPT_HASH_HANDLE hash{};
    std::string result;
    if (BCryptOpenAlgorithmProvider(&algorithm, BCRYPT_SHA256_ALGORITHM, nullptr, 0) >= 0) {
        DWORD size{}, received{};
        if (BCryptGetProperty(algorithm, BCRYPT_OBJECT_LENGTH, reinterpret_cast<PUCHAR>(&size),
                             sizeof(size), &received, 0) >= 0) {
            std::vector<unsigned char> object(size);
            if (BCryptCreateHash(algorithm, &hash, object.data(), size, nullptr, 0, 0) >= 0) {
                std::array<unsigned char, 65536> buffer{}; bool good = true;
                for (;;) {
                    if (!ReadFile(file, buffer.data(), static_cast<DWORD>(buffer.size()), &received, nullptr)) { good = false; break; }
                    if (!received) break;
                    if (BCryptHashData(hash, buffer.data(), received, 0) < 0) { good = false; break; }
                }
                std::array<unsigned char, 32> digest{};
                if (good && BCryptFinishHash(hash, digest.data(), static_cast<ULONG>(digest.size()), 0) >= 0) {
                    constexpr char hex[] = "0123456789abcdef";
                    for (auto value : digest) { result += hex[value >> 4]; result += hex[value & 15]; }
                }
                // BCrypt retains the supplied object buffer until DestroyHash.
                BCryptDestroyHash(hash); hash = nullptr;
            }
        }
        BCryptCloseAlgorithmProvider(algorithm, 0);
    }
    CloseHandle(file);
    return result;
}

static void Status(const char* phase) {
    HMODULE self{};
    if (!GetModuleHandleExA(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS | GET_MODULE_HANDLE_EX_FLAG_UNCHANGED_REFCOUNT,
                            reinterpret_cast<LPCSTR>(&Status), &self)) return;
    char path[32768]{};
    if (!GetModuleFileNameA(self, path, sizeof(path))) return;
    std::string target = std::string(path) + ".status.json";
    std::string temporary = target + ".tmp";
    FILE* file{};
    if (fopen_s(&file, temporary.c_str(), "wb") != 0) return;
    std::fprintf(file, "{\"phase\":\"%s\",\"pid\":%lu,\"build\":6819,\"dev\":true,\"insecure\":true,\"walker_commands_registered\":%s}\n", phase, GetCurrentProcessId(),std::strcmp(phase,"registered")==0?"true":"false");
    std::fclose(file);
    MoveFileExA(temporary.c_str(), target.c_str(), MOVEFILE_REPLACE_EXISTING | MOVEFILE_WRITE_THROUGH);
}

static BOOL CALLBACK Initialize(PINIT_ONCE, PVOID, PVOID*) {
    if (!CommandLine()->HasParm("-dev") || !CommandLine()->HasParm("-insecure"))
        Plat_FatalError("CitadelCast test unlocker requires explicit -dev -insecure.");
    char tier_path[32768]{};
    if (!GetModuleFileNameA(GetModuleHandleW(L"tier0.dll"), tier_path, sizeof(tier_path)) || CitadelCastHashFile(tier_path) != kTierHash)
        Plat_FatalError("CitadelCast unlocker refused unreviewed Tier0.");
    std::string path = std::string(Plat_GetGameDirectory()) + "\\citadel\\bin\\win64\\server.dll";
    if (CitadelCastHashFile(path.c_str()) != kServerHash)
        Plat_FatalError("CitadelCast unlocker refused unreviewed server build.");
    real_module = LoadLibraryA(path.c_str());
    real_factory = real_module ? reinterpret_cast<CreateInterfaceFn>(GetProcAddress(real_module, "CreateInterface")) : nullptr;
    if (!real_factory) Plat_FatalError("CitadelCast unlocker could not load the reviewed local server interface.");
    Status("loaded");
    return TRUE;
}

static bool VerifyCvar() {
    if (!g_pCVar || g_pCVar != cvar) return false;
    const auto base = reinterpret_cast<std::uintptr_t>(GetModuleHandleW(L"tier0.dll"));
    auto table = *reinterpret_cast<std::uintptr_t**>(g_pCVar);
    if (reinterpret_cast<std::uintptr_t>(table) != base + kCvarTable) return false;
    for (std::size_t slot = 0; slot < kCvarSlots.size(); ++slot)
        if (table[slot] != base + kCvarSlots[slot]) return false;
    return true;
}

static bool Connect(IAppSystem* app, CreateInterfaceFn factory) {
    AcquireSRWLockExclusive(&registration_lock);
    const bool ok = reinterpret_cast<bool(*)(IAppSystem*, CreateInterfaceFn)>(original_connect)(app, factory);
    const bool result = registration.connect(ok, [&] {
        ConnectInterfaces(&factory, 1);
        if (!VerifyCvar()) {
            DisconnectInterfaces();
            Plat_FatalError("CitadelCast unlocker refused an unreviewed command-registry interface.");
        }
        ConVar_Register(FCVAR_RELEASE | FCVAR_GAMEDLL);
        if (!RegisterWalkerCommands())
            Plat_FatalError("CitadelCast could not register its independent client camera commands.");
    });
    ReleaseSRWLockExclusive(&registration_lock);
    if (result) {
        Status("registered");
        Msg("CitadelCast Walker adapter and unlocker registered for reviewed build6819 (-dev -insecure).\n");
    }
    return result;
}

static void Disconnect(IAppSystem* app) {
    AcquireSRWLockExclusive(&registration_lock);
    registration.disconnect([] {
        ShutdownWalker();
        UnregisterUnlockerCommands();
        ConVar_Unregister();
        DisconnectInterfaces();
    }, [&] { reinterpret_cast<void(*)(IAppSystem*)>(original_disconnect)(app); });
    ReleaseSRWLockExclusive(&registration_lock);
    Status("disconnected");
}

#undef CreateInterface
DLL_EXPORT void* CreateInterface(const char* name, int* result) {
    if (!InitOnceExecuteOnce(&once, Initialize, nullptr, nullptr)) return nullptr;
    void* object = real_factory(name, result);
    if (std::strcmp(name, "Source2ServerConfig001") != 0) return object;
    AcquireSRWLockExclusive(&hook_lock);
    if (object != hooked_config) {
        auto base = reinterpret_cast<std::uintptr_t>(real_module);
        auto table = object ? *reinterpret_cast<std::uintptr_t**>(object) : nullptr;
        if (hooked_config || !table || reinterpret_cast<std::uintptr_t>(table) != base + kConfigTable ||
            table[0] != base + kConfigConnect || table[1] != base + kConfigDisconnect || table[13] != base + kConfigInterval)
            Plat_FatalError("CitadelCast unlocker refused an unreviewed Source2ServerConfig001 object.");
        if (!InstallOwnedPair(reinterpret_cast<void**>(table), reinterpret_cast<void*>(&Connect),
                              reinterpret_cast<void*>(&Disconnect), &original_connect, &original_disconnect))
            Plat_FatalError("CitadelCast unlocker could not install its startup/cleanup callbacks.");
        hooked_config = static_cast<IAppSystem*>(object);
    }
    ReleaseSRWLockExclusive(&hook_lock);
    return object;
}
