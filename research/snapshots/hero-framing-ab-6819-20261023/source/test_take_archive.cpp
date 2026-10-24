#include "take_archive.hpp"
#include <cassert>
#include <map>
#include <string>
#include <cstdio>
int main(){
    hero::TakeArchive a;std::map<unsigned long long,std::string> records;
    unsigned writes=0;std::string profile="turn-with-hero";
    auto save=[&](auto id){++writes;return records.emplace(id,profile).second;};
    assert(a.publish(save)&&writes==0);assert(a.arm()&&!a.arm());
    assert(a.publish(save)&&writes==0);a.finish();
    assert(a.pending()&&!a.arm());assert(!a.publish([](auto){return false;}));
    assert(a.pending()&&!a.arm());assert(a.publish(save)&&writes==1&&!a.pending());
    a.finish();assert(a.publish(save)&&writes==1); // duplicate stop/status cannot overwrite
    profile="hold-bearing";assert(a.arm()&&a.id()==2);a.finish();assert(a.publish(save));
    assert(records.size()==2&&records[1]=="turn-with-hero"&&records[2]=="hold-bearing");
    assert(a.arm());a.finish();records.emplace(3,"existing");
    assert(!a.publish(save)&&a.pending()&&!a.arm()&&records[3]=="existing");
    std::puts("take_archive: unique A/B records, stop-only publication, no overwrite, failed-save retry and next-take blocking passed");
}
