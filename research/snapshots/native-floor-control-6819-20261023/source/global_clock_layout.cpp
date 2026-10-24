// Layout-only executable: no native constructors/functions or game access.
#include "globalvars_base.h"
#include <cstddef>
#include <cstdio>
static_assert(offsetof(CGlobalVarsBase,curtime)==0x30);
static_assert(offsetof(CGlobalVarsBase,frametime)==0x34);
static_assert(offsetof(CGlobalVarsBase,m_bInSimulation)==0x40);
static_assert(offsetof(CGlobalVarsBase,tickcount)==0x44);
int main(){std::puts("SDK partial globals layout corroborates curtime+0x30,frametime+0x34,simulation+0x40,tickcount+0x44. No complete globals ABI is claimed.");}
