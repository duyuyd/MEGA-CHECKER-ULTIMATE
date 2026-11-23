package vn.nptduy.localpasswordlab;

import java.util.concurrent.atomic.AtomicBoolean;

public final class EngineSelfTest {
    private static void check(boolean ok, String message) {
        if (!ok) throw new AssertionError(message);
    }

    public static void main(String[] args) {
        check(CandidateEngine.normalizeAlphabet("aaBbππ•√")[3] == 'π',
                "Unicode alphabet must deduplicate and retain order");
        CandidateEngine.Report exact = CandidateEngine.run("ab", "ba", 100, null, () -> false);
        check(exact.matchedReference && exact.attempts == 5, "Known local reference 'ba'");
        CandidateEngine.Report unicode = CandidateEngine.run("π√", "√π", 100, null, () -> false);
        check(unicode.matchedReference && unicode.attempts == 5, "Unicode reference");
        CandidateEngine.Report missing = CandidateEngine.run("abcd", "đ", 100, null, () -> false);
        check(!missing.matchedReference && missing.attempts == 100, "Unmatched sample must not be invented");
        CandidateEngine.Report million = CandidateEngine.run("Qwertyuiopasdgfjklzxvbnm1234567890π√×€",
                null, CandidateEngine.MAX_TRIALS, null, () -> false);
        check(million.attempts == 1_000_000, "Measured actual million iterations");
        check(million.rate > 0 && million.elapsedNanos > 0, "Real timing");
        AtomicBoolean stop = new AtomicBoolean(true);
        CandidateEngine.Report cancelled = CandidateEngine.run("abcd", null, 1_000_000, null, stop::get);
        check(cancelled.cancelled && cancelled.attempts == 0, "Cancellation");
        try {
            CandidateEngine.run("a", null, 2, null, () -> false);
            throw new AssertionError("One-symbol alphabet accepted");
        } catch (IllegalArgumentException expected) {}
        try {
            CandidateEngine.run("ab", null, 1_000_001, null, () -> false);
            throw new AssertionError("Exceeded hard limit");
        } catch (IllegalArgumentException expected) {}
        try {
            CandidateEngine.run("ab", "a".repeat(33), 10, null, () -> false);
            throw new AssertionError("Overlong reference accepted");
        } catch (IllegalArgumentException expected) {}
        System.out.println("PASS: 9 independent local engine checks; 1,000,000 actual synthetic comparisons");
    }
}
