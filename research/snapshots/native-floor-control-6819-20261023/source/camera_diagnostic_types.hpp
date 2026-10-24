#pragma once
#include <cstdint>
struct CameraTypeName { std::uintptr_t table; const char* name; };
constexpr std::uintptr_t kDiagnosticClientImageSize=0x43bf000;
constexpr CameraTypeName kDiagnosticCameraTypes[]={
    {0x277d030,"CCitadelCameraManager"},
    {0x2c039c0,"CBaseCameraManager"},
    {0x2c36160,"CDataDrivenCamera"},
    {0x2784a98,"CCitadel_ThirdPersonCamera"},
    {0x2c03f10,"CNoClipCamera"},
    {0x2c03d38,"CFreeCamera"},
    {0x277d9d8,"C_Citadel_HLTVCamera"},
    {0x2c0eb40,"C_HLTVCamera"},
    {0x2c040d8,"CSimpleCamera"},
    {0x2c03810,"CBaseCamera"},
    {0x277c788,"CCitadel_Camera"},
    {0x2c03b78,"CBaseAnimatingCamera"},
};
