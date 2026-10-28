// Test helper for tests/test_hdtex.py: builds against tools/hdtex/hdtex.hpp.
//   hdtex_check hash <file> <chunk>      the upload hash of the file, fed in pieces of <chunk> bytes
//   hdtex_check dds <file> <out.raw>     decode a .dds to w, h (u32) and RGBA pixels
//   hdtex_check store <map> <n>          the picture loader: preloads, urgent requests, hand-over order, forget and ask again
#include "hdtex.hpp"
#include <cstdio>
#include <chrono>
#include <cstdlib>
#include <thread>
#include <string>
#include <vector>
static std::vector<std::uint8_t> slurp(const char *p) {
    std::vector<std::uint8_t> d;
    FILE *f = std::fopen(p, "rb");
    if (!f) return d;
    std::uint8_t b[65536];
    std::size_t g;
    while ((g = std::fread(b, 1, sizeof b, f)) > 0) d.insert(d.end(), b, b + g);
    std::fclose(f);
    return d;
}
int main(int argc, char **argv) {
    if (argc < 4) return 2;
    std::string m = argv[1];
    if (m == "store") {
        hdtex::Store st;
        const std::size_t n = st.load(argv[2]);
        const int want = std::atoi(argv[3]);
        if (static_cast<int>(n) != want) return 3;
        auto wait_all = [&](int count, bool low, std::vector<int> &got) {
            for (int tries = 0; tries < 400 && static_cast<int>(got.size()) < count; ++tries) {
                int e;
                hdtex::Image img;
                while (st.poll(e, img, low)) {
                    if (img.w != 64 || img.h != 64) return false;
                    got.push_back(e);
                }
                std::this_thread::sleep_for(std::chrono::milliseconds(10));
            }
            return static_cast<int>(got.size()) == count;
        };
        // preloads wait in the low queue: nothing is handed over unless asked for
        for (int i = 0; i < 3; ++i) st.request(i, false);
        std::this_thread::sleep_for(std::chrono::milliseconds(300));
        std::vector<int> got;
        int e;
        hdtex::Image img;
        if (st.poll(e, img, false)) return 4;
        // the game asks for one of them: it comes out at once, the others only when preloads are allowed
        st.request(1, true);
        if (!st.poll(e, img, false) || e != 1) return 5;
        if (!wait_all(2, true, got)) return 6;
        // urgent and preload requests all finish
        got.clear();
        st.request(3, false);
        st.request(4, false);
        st.request(5, true);
        if (!wait_all(3, true, got)) return 7;
        // forgetting a decoded picture lets it be asked for again
        st.forget(1);
        st.request(1, true);
        got.clear();
        if (!wait_all(1, false, got) || got[0] != 1) return 8;
        // a request twice is one decode
        st.request(2, true);
        st.request(2, true);
        std::this_thread::sleep_for(std::chrono::milliseconds(100));
        if (st.poll(e, img, true)) return 9;
        // waiting for a picture that is being decoded: ready in time, and picked up by poll
        st.forget(2);
        st.request(6, true);
        if (!st.wait_ready(6, 5000)) return 10;
        if (!st.poll(e, img, false) || e != 6) return 11;
        // an entry nobody asked for never becomes ready
        if (st.wait_ready(7, 30)) return 12;
        std::printf("store ok\n");
        return 0;
    }
    auto d = slurp(argv[2]);
    if (m == "hash") {
        std::size_t chunk = static_cast<std::size_t>(std::atoi(argv[3]));
        hdtex::Hasher h;
        h.begin(d.size());
        std::uint64_t key = 0;
        bool done = false;
        for (std::size_t i = 0; i < d.size(); i += chunk) done = h.feed(d.data() + i, std::min(chunk, d.size() - i), key) || done;
        if (!done) return 3;
        std::printf("%016llx\n", static_cast<unsigned long long>(key));
        return 0;
    }
    if (m == "dds") {
        hdtex::Image img;
        std::string e = hdtex::decode_dds(d.data(), d.size(), img);
        if (!e.empty()) {
            std::printf("ERR %s\n", e.c_str());
            return 1;
        }
        FILE *o = std::fopen(argv[3], "wb");
        std::fwrite(&img.w, 4, 1, o);
        std::fwrite(&img.h, 4, 1, o);
        std::fwrite(img.px.data(), 4, img.px.size(), o);
        std::fclose(o);
        return 0;
    }
    return 2;
}
