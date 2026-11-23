package vn.nptduy.localpasswordlab;

import android.app.Activity;
import android.content.res.ColorStateList;
import android.graphics.Color;
import android.graphics.Typeface;
import android.graphics.drawable.GradientDrawable;
import android.os.Bundle;
import android.text.InputType;
import android.view.View;
import android.view.WindowManager;
import android.view.inputmethod.EditorInfo;
import android.widget.Button;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.ProgressBar;
import android.widget.ScrollView;
import android.widget.TextView;
import java.text.NumberFormat;
import java.util.Locale;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.atomic.AtomicBoolean;

/** Isolated local-only educational passphrase lab; never accesses Google accounts. */
public final class MainActivity extends Activity {
    // Preset derived from requested keyboard characters; duplicate characters are removed
    // by CandidateEngine, while Unicode symbols are preserved.
    private static final String PRESET = "Qwertyuiopasdgfjklzxvbnm"
            + "1234567890"
            + "~`|•√π÷×¶∆@#$%&-+()/*\"':;!?"
            + "£¢€¥^°={}…\\©®™℅[]"
            + "QWERTYUIOPASDFGHJKLZXCVBNM";
    private static final int INK = Color.rgb(29, 38, 64);
    private static final int BLUE = Color.rgb(37, 78, 171);
    private static final int MUTED = Color.rgb(91, 106, 130);
    private static final int LIGHT = Color.rgb(236, 242, 255);
    private final ExecutorService executor = Executors.newSingleThreadExecutor();
    private final NumberFormat number = NumberFormat.getIntegerInstance(Locale.forLanguageTag("vi-VN"));

    private EditText reference, alphabet;
    private Button benchmark, compare, cancel;
    private ProgressBar progressBar;
    private TextView result;
    private int serial;
    private volatile boolean running;
    private AtomicBoolean cancellation;

    @Override public void onCreate(Bundle state) {
        super.onCreate(state);
        getWindow().addFlags(WindowManager.LayoutParams.FLAG_SECURE);
        getWindow().setSoftInputMode(WindowManager.LayoutParams.SOFT_INPUT_ADJUST_RESIZE);

        ScrollView scroll = new ScrollView(this);
        scroll.setFillViewport(true);
        scroll.setFitsSystemWindows(true);
        scroll.setBackgroundColor(Color.rgb(248, 250, 255));
        LinearLayout stack = new LinearLayout(this);
        stack.setOrientation(LinearLayout.VERTICAL);
        stack.setPadding(dp(18), dp(22), dp(18), dp(28));
        stack.setFocusableInTouchMode(true);
        scroll.addView(stack);

        TextView title = text("NPT LOCAL PASSWORD LAB", 22, true, INK);
        add(stack, title, 0);
        add(stack, text("1.000.000 lượt thử • offline • Android", 14, true, BLUE), 5);
        add(stack, text(
                "Ứng dụng chỉ thử tổ hợp với CHUỖI MẪU do bạn tự đặt. Không thể xác định "
                + "mật khẩu Gmail từ địa chỉ email và không kết nối tài khoản Google.", 13, false, MUTED), 14);

        add(stack, text("Chuỗi mẫu cục bộ (KHÔNG nhập mật khẩu Gmail thật)", 14, true, INK), 20);
        reference = new EditText(this);
        reference.setId(R.id.sample_input);
        reference.setSingleLine(true);
        reference.setTextSize(16);
        reference.setTextColor(INK);
        reference.setHint("Đặt một chuỗi mẫu để kiểm tra");
        reference.setInputType(InputType.TYPE_CLASS_TEXT
                | InputType.TYPE_TEXT_VARIATION_PASSWORD | InputType.TYPE_TEXT_FLAG_NO_SUGGESTIONS);
        reference.setImeOptions(EditorInfo.IME_ACTION_DONE | EditorInfo.IME_FLAG_NO_PERSONALIZED_LEARNING);
        reference.setSaveEnabled(false);
        if (android.os.Build.VERSION.SDK_INT >= 26) {
            reference.setImportantForAutofill(View.IMPORTANT_FOR_AUTOFILL_NO_EXCLUDE_DESCENDANTS);
        }
        reference.setBackground(surface(Color.WHITE, Color.rgb(185, 199, 226)));
        reference.setPadding(dp(12), dp(10), dp(12), dp(10));
        add(stack, reference, 6);

        add(stack, text("Bảng ký tự tùy chỉnh (hỗ trợ Unicode)", 14, true, INK), 14);
        alphabet = new EditText(this);
        alphabet.setId(R.id.alphabet_input);
        alphabet.setSingleLine(false);
        alphabet.setMinLines(2);
        alphabet.setMaxLines(4);
        alphabet.setTextSize(14);
        alphabet.setTextColor(INK);
        alphabet.setInputType(InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_FLAG_MULTI_LINE
                | InputType.TYPE_TEXT_FLAG_NO_SUGGESTIONS);
        alphabet.setText(PRESET);
        alphabet.setSaveEnabled(false);
        alphabet.setBackground(surface(Color.WHITE, Color.rgb(185, 199, 226)));
        alphabet.setPadding(dp(12), dp(10), dp(12), dp(10));
        add(stack, alphabet, 6);

        benchmark = button("Đo đúng 1.000.000 lượt", R.id.benchmark_button, true);
        add(stack, benchmark, 16);
        benchmark.setOnClickListener(v -> start(false));

        compare = button("So khớp chuỗi mẫu", R.id.compare_button, true);
        add(stack, compare, 7);
        compare.setOnClickListener(v -> start(true));

        cancel = button("Dừng phép thử", R.id.cancel_button, false);
        add(stack, cancel, 7);
        cancel.setEnabled(false);
        cancel.setOnClickListener(v -> {
            if (cancellation != null) cancellation.set(true);
        });

        progressBar = new ProgressBar(this, null, android.R.attr.progressBarStyleHorizontal);
        progressBar.setId(R.id.progress_bar);
        progressBar.setMax(1_000_000);
        progressBar.setProgress(0);
        add(stack, progressBar, 17);
        result = text("Sẵn sàng. Mọi phép thử được thực hiện ngay trên thiết bị.", 14, false, INK);
        result.setId(R.id.result_text);
        result.setSaveEnabled(false);
        result.setAccessibilityLiveRegion(View.ACCESSIBILITY_LIVE_REGION_POLITE);
        result.setBackground(surface(LIGHT, Color.rgb(221, 229, 248)));
        result.setPadding(dp(14), dp(12), dp(14), dp(12));
        add(stack, result, 10);
        add(stack, text("Dữ liệu không lưu lại, không gửi mạng, không thử đăng nhập. "
                + "Kết quả trùng khớp chỉ xác nhận chuỗi mẫu bạn đã nhập.", 12, false, MUTED), 12);
        setContentView(scroll);
    }

    private void start(boolean compareToReference) {
        if (running) return;
        final String requestedAlphabet = alphabet.getText().toString();
        final String sample = compareToReference ? reference.getText().toString() : null;
        try {
            CandidateEngine.normalizeAlphabet(requestedAlphabet);
            if (compareToReference && (sample.isEmpty() || sample.codePointCount(0, sample.length())
                    > CandidateEngine.MAX_LENGTH)) {
                throw new IllegalArgumentException("Nhập chuỗi mẫu có từ 1 đến 32 ký tự.");
            }
        } catch (IllegalArgumentException ex) {
            result.setText(ex.getMessage());
            return;
        }
        running = true;
        final int ticket = ++serial;
        final AtomicBoolean abort = new AtomicBoolean(false);
        cancellation = abort;
        benchmark.setEnabled(false);
        compare.setEnabled(false);
        cancel.setEnabled(true);
        progressBar.setProgress(0);
        result.setText("Đang đo thực tế trên thiết bị, tối đa 1.000.000 lượt...");
        executor.execute(() -> {
            try {
                CandidateEngine.Report report = CandidateEngine.run(requestedAlphabet, sample,
                        CandidateEngine.MAX_TRIALS, value ->
                                runOnUiThread(() -> {
                                    if (ticket == serial && running) {
                                        progressBar.setProgress((int) value);
                                        result.setText("Đã thử " + number.format(value) + " lượt...");
                                    }
                                }), abort::get);
                runOnUiThread(() -> {
                    if (ticket != serial || isDestroyed()) return;
                    progressBar.setProgress((int) report.attempts);
                    final String status;
                    if (report.cancelled) {
                        status = "Đã dừng theo yêu cầu.";
                    } else if (compareToReference && report.matchedReference) {
                        status = "TRÙNG KHỚP CHUỖI MẪU CỤC BỘ. Không phải xác nhận Gmail.";
                    } else if (compareToReference) {
                        status = "Không tìm thấy chuỗi mẫu trong số lượt đã thử. "
                                + "Không thể suy ra mật khẩu Gmail.";
                    } else {
                        status = "Đã hoàn thành đo 1.000.000 lượt trên thiết bị.";
                    }
                    double millis = report.elapsedNanos / 1_000_000.0;
                    result.setText(status + "\nSố lượt: " + number.format(report.attempts)
                            + "\nTốc độ đo: " + number.format(report.rate) + " lượt/giây"
                            + "\nThời gian: " + String.format(Locale.US, "%.2f", millis) + " ms"
                            + "\nKích thước bảng: " + report.alphabetSize + " ký tự");
                    // Clear sample promptly after an audit, never echo its value.
                    if (compareToReference) reference.setText("");
                    setBusy(false);
                });
            } catch (Exception ex) {
                runOnUiThread(() -> {
                    if (ticket != serial || isDestroyed()) return;
                    result.setText("Không thể chạy phép thử: " + ex.getMessage());
                    reference.setText("");
                    setBusy(false);
                });
            }
        });
    }

    private void setBusy(boolean busy) {
        running = busy;
        benchmark.setEnabled(!busy);
        compare.setEnabled(!busy);
        cancel.setEnabled(busy);
        if (!busy) cancellation = null;
    }

    @Override protected void onStop() {
        super.onStop();
        ++serial;
        if (cancellation != null) cancellation.set(true);
        setBusy(false);
        if (reference != null) reference.setText("");
        if (result != null) result.setText("Đã xóa kết quả khi rời ứng dụng.");
        if (progressBar != null) progressBar.setProgress(0);
    }

    @Override protected void onDestroy() {
        executor.shutdownNow();
        super.onDestroy();
    }

    private int dp(int value) {
        return Math.round(value * getResources().getDisplayMetrics().density);
    }

    private GradientDrawable surface(int fill, int outline) {
        GradientDrawable background = new GradientDrawable();
        background.setColor(fill);
        background.setCornerRadius(dp(12));
        background.setStroke(dp(1), outline);
        return background;
    }

    private TextView text(String label, int size, boolean bold, int color) {
        TextView view = new TextView(this);
        view.setText(label);
        view.setTextSize(size);
        view.setTextColor(color);
        view.setTypeface(Typeface.create("sans-serif", bold ? Typeface.BOLD : Typeface.NORMAL));
        return view;
    }

    private Button button(String label, int id, boolean primary) {
        Button view = new Button(this);
        view.setId(id);
        view.setText(label);
        view.setAllCaps(false);
        view.setTextSize(15);
        view.setMinHeight(dp(45));
        view.setBackgroundTintList(null);
        view.setBackground(surface(primary ? BLUE : LIGHT, primary ? BLUE : Color.rgb(195, 207, 231)));
        view.setTextColor(new ColorStateList(
                new int[][] {new int[] {-android.R.attr.state_enabled}, new int[] {}},
                new int[] {primary ? Color.rgb(186, 203, 234) : MUTED, primary ? Color.WHITE : INK}));
        return view;
    }

    private void add(LinearLayout root, View view, int marginTop) {
        LinearLayout.LayoutParams params = new LinearLayout.LayoutParams(-1, -2);
        params.topMargin = dp(marginTop);
        root.addView(view, params);
    }
}
