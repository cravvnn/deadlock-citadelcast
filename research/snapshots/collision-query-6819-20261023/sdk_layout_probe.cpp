// OFFLINE ONLY: compile existing SDK declarations; no game imports, process
// access, native calls, constructors, filter instances or camera operations.
#include "gametrace.h"
#include <cstddef>
#include <cstdio>
#include <type_traits>
// Layout corroboration against the pinned native constructors/consumers. This
// does not establish runtime phase, world lifetime or collision-layer meaning.
static_assert(sizeof(Ray_t)==0x30 && alignof(Ray_t)==8);
static_assert(offsetof(Ray_t,m_eType)==0x28);
static_assert(sizeof(CTraceFilter)==0x48);
static_assert(offsetof(CTraceFilter,m_nInteractsWith)==8);
static_assert(offsetof(CTraceFilter,m_nInteractsExclude)==0x10);
static_assert(offsetof(CTraceFilter,m_nInteractsAs)==0x18);
static_assert(offsetof(CTraceFilter,m_nEntityIdsToIgnore)==0x20);
static_assert(offsetof(CTraceFilter,m_nOwnerIdsToIgnore)==0x28);
static_assert(offsetof(CTraceFilter,m_nHierarchyIds)==0x30);
static_assert(offsetof(CTraceFilter,m_nIncludedDetailLayers)==0x34);
static_assert(offsetof(CTraceFilter,m_nObjectSetMask)==0x37);
static_assert(offsetof(CTraceFilter,m_nCollisionGroup)==0x38);
static_assert(offsetof(CTraceFilter,m_bIterateEntities)==0x40);
static_assert(sizeof(CGameTrace)==0xc0 && alignof(CGameTrace)==16);
static_assert(offsetof(CGameTrace,m_vStartPos)==0x78);
static_assert(offsetof(CGameTrace,m_vEndPos)==0x84);
static_assert(offsetof(CGameTrace,m_flFraction)==0xac);
static_assert(offsetof(CGameTrace,m_eRayType)==0xba);
static_assert(offsetof(CGameTrace,m_bStartInSolid)==0xbb);
static_assert(offsetof(CGameTrace,m_bExactHitPoint)==0xbc);
static_assert(std::is_trivially_destructible_v<CGameTrace>);
#define SIZE(T) std::printf("%s.size=%zu align=%zu\n", #T, sizeof(T), alignof(T))
#define OFFSET(T, F) std::printf("%s.%s=%zu\n", #T, #F, offsetof(T, F))
int main() {
    SIZE(Ray_t); OFFSET(Ray_t, m_eType);
    SIZE(RnQueryShapeAttr_t); SIZE(CTraceFilter);
    OFFSET(CTraceFilter, m_nInteractsWith);
    OFFSET(CTraceFilter, m_nInteractsExclude);
    OFFSET(CTraceFilter, m_nInteractsAs);
    OFFSET(CTraceFilter, m_nEntityIdsToIgnore);
    OFFSET(CTraceFilter, m_nOwnerIdsToIgnore);
    OFFSET(CTraceFilter, m_nHierarchyIds);
    OFFSET(CTraceFilter, m_nIncludedDetailLayers);
    OFFSET(CTraceFilter, m_nTargetDetailLayer);
    OFFSET(CTraceFilter, m_nObjectSetMask);
    OFFSET(CTraceFilter, m_nCollisionGroup);
    OFFSET(CTraceFilter, m_bIterateEntities);
    SIZE(RnCollisionAttr_t); SIZE(CGameTrace);
    OFFSET(CGameTrace, m_pEnt);
    OFFSET(CGameTrace, m_BodyTransform);
    OFFSET(CGameTrace, m_ShapeAttributes);
    OFFSET(CGameTrace, m_vStartPos);
    OFFSET(CGameTrace, m_vEndPos);
    OFFSET(CGameTrace, m_vHitNormal);
    OFFSET(CGameTrace, m_vHitPoint);
    OFFSET(CGameTrace, m_flHitOffset);
    OFFSET(CGameTrace, m_flFraction);
    OFFSET(CGameTrace, m_nTriangle);
    OFFSET(CGameTrace, m_eRayType);
    OFFSET(CGameTrace, m_bStartInSolid);
    OFFSET(CGameTrace, m_bExactHitPoint);
    std::printf("CGameTrace.trivially_destructible=%d\n",
        std::is_trivially_destructible_v<CGameTrace>);
}
