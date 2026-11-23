package vn.nptduy.localpasswordlab;

import java.util.LinkedHashSet;

/**
 * Offline and bounded synthetic combination evaluator.
 * Accepts a reference phrase explicitly supplied by the user.
 * Never queries Gmail, Google, remote accounts, password hashes, or saved credentials.
 */
public final class CandidateEngine {
    public static final long MAX_TRIALS = 1_000_000L;
    public static final int MAX_LENGTH = 32;
    public static final int MAX_ALPHABET = 512;
    private static volatile int lastChecksum;

    public interface Progress {
        void update(long count);
    }

    public interface Cancelled {
        boolean isCancelled();
    }

    public static final class Report {
        public final long attempts;
        public final long elapsedNanos;
        public final long rate;
        public final int alphabetSize;
        public final boolean matchedReference;
        public final boolean cancelled;

        private Report(long attempts, long elapsedNanos, int alphabetSize, boolean match, boolean cancel) {
            this.attempts = attempts;
            this.elapsedNanos = Math.max(1, elapsedNanos);
            this.rate = attempts * 1_000_000_000L / this.elapsedNanos;
            this.alphabetSize = alphabetSize;
            this.matchedReference = match;
            this.cancelled = cancel;
        }
    }

    private CandidateEngine() {}

    public static int[] normalizeAlphabet(String raw) {
        if (raw == null) throw new IllegalArgumentException("Chưa có bảng ký tự.");
        LinkedHashSet<Integer> unique = new LinkedHashSet<>();
        raw.codePoints().filter(cp -> !Character.isWhitespace(cp)).forEach(unique::add);
        if (unique.size() < 2 || unique.size() > MAX_ALPHABET) {
            throw new IllegalArgumentException("Bảng ký tự phải có từ 2 đến 512 ký tự khác nhau.");
        }
        return unique.stream().mapToInt(Integer::intValue).toArray();
    }

    public static Report run(String rawAlphabet, String reference, long limit,
                             Progress progress, Cancelled cancelled) {
        if (limit < 1 || limit > MAX_TRIALS) {
            throw new IllegalArgumentException("Số lần thử phải từ 1 đến 1.000.000.");
        }
        final int[] alphabet = normalizeAlphabet(rawAlphabet);
        final int[] desired = reference == null ? null : reference.codePoints().toArray();
        if (desired != null && (desired.length == 0 || desired.length > MAX_LENGTH)) {
            throw new IllegalArgumentException("Chuỗi mẫu phải có từ 1 đến 32 ký tự.");
        }
        final long started = System.nanoTime();
        long attempts = 0L;
        int checksum = 0;

        for (int length = 1; length <= MAX_LENGTH && attempts < limit; length++) {
            long combinations = 1L;
            for (int pos = 0; pos < length; pos++) {
                if (combinations > limit / alphabet.length) {
                    combinations = limit;
                    break;
                }
                combinations *= alphabet.length;
            }
            final long thisLength = Math.min(combinations, limit - attempts);
            for (long ordinal = 0; ordinal < thisLength; ordinal++) {
                if (cancelled != null && cancelled.isCancelled()) {
                    lastChecksum = checksum;
                    return new Report(attempts, System.nanoTime() - started, alphabet.length, false, true);
                }
                long digits = ordinal;
                boolean equal = desired != null && desired.length == length;
                int tokenHash = 1;
                // Evaluate actual code-point combinations; do not log or store them.
                for (int pos = length - 1; pos >= 0; pos--) {
                    final int candidateCodePoint = alphabet[(int) (digits % alphabet.length)];
                    digits /= alphabet.length;
                    tokenHash = tokenHash * 31 + candidateCodePoint;
                    if (equal && desired[pos] != candidateCodePoint) equal = false;
                }
                checksum ^= tokenHash;
                attempts++;
                if (equal) {
                    lastChecksum = checksum;
                    return new Report(attempts, System.nanoTime() - started, alphabet.length, true, false);
                }
                if (progress != null && attempts % 20_000L == 0L) {
                    progress.update(attempts);
                }
            }
        }
        lastChecksum = checksum;
        return new Report(attempts, System.nanoTime() - started, alphabet.length, false, false);
    }
}
