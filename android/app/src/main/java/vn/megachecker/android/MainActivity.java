package vn.megachecker.android;

import android.app.Activity;
import android.os.Build;
import android.os.Bundle;
import android.content.Context;
import android.content.res.ColorStateList;
import android.graphics.Color;
import android.graphics.Typeface;
import android.graphics.drawable.GradientDrawable;
import android.text.Editable;
import android.text.InputType;
import android.text.TextWatcher;
import android.view.View;
import android.view.WindowManager;
import android.view.inputmethod.EditorInfo;
import android.view.inputmethod.InputMethodManager;
import android.widget.Button;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;
import com.chaquo.python.Python;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.Future;

public final class MainActivity extends Activity {
    private static final int INK = Color.rgb(23, 61, 53);
    private static final int TEAL = Color.rgb(0, 104, 83);
    private static final int PALE = Color.rgb(226, 238, 230);
    private static final int PAPER = Color.rgb(244, 247, 244);
    private final ExecutorService workers = Executors.newFixedThreadPool(2);
    private LinearLayout page;
    private TextView heading, instructions, networkNotice, result;
    private EditText field;
    private Button passwordTab, emailTab, speedTab, local, online;
    private boolean password = true;
    private boolean speedMode = false;
    private long revision;
    private Future<?> pending;

    @Override public void onCreate(Bundle state) {
        super.onCreate(state);
        getWindow().addFlags(WindowManager.LayoutParams.FLAG_SECURE);
        ScrollView scroller = new ScrollView(this);
        scroller.setFillViewport(true);
        scroller.setFitsSystemWindows(true);
        scroller.setBackgroundColor(PAPER);
        page = new LinearLayout(this);
        page.setOrientation(LinearLayout.VERTICAL);
        page.setPadding(dp(22), dp(22), dp(22), dp(24));
        page.setFocusableInTouchMode(true);
        scroller.addView(page);
        setContentView(scroller);

        TextView brand = label(18, true);
        brand.setText("MEGA Checker");
        brand.setCompoundDrawablesWithIntrinsicBounds(R.drawable.ic_app, 0, 0, 0);
        brand.setCompoundDrawablePadding(dp(12));
        row(brand, 0);

        LinearLayout tabs = new LinearLayout(this);
        tabs.setOrientation(LinearLayout.HORIZONTAL);
        passwordTab = button("Mật khẩu", R.id.tab_password);
        emailTab = button("Email", R.id.tab_email);
        speedTab = button("Tốc độ", R.id.tab_speed);
        tabs.addView(passwordTab, new LinearLayout.LayoutParams(0, dp(48), 1));
        LinearLayout.LayoutParams second = new LinearLayout.LayoutParams(0, dp(48), 1);
        second.setMargins(dp(8), 0, 0, 0);
        tabs.addView(emailTab, second);
        LinearLayout.LayoutParams third = new LinearLayout.LayoutParams(0, dp(48), 1);
        third.setMargins(dp(8), 0, 0, 0);
        tabs.addView(speedTab, third);
        row(tabs, 20);
        passwordTab.setOnClickListener(v -> select(true));
        emailTab.setOnClickListener(v -> select(false));
        speedTab.setOnClickListener(v -> selectSpeed());

        heading = label(29, true);
        row(heading, 22);
        instructions = label(15, false);
        row(instructions, 4);
        field = new EditText(this);
        field.setId(R.id.field);
        field.setSingleLine(true);
        field.setTextSize(18);
        field.setTextColor(INK);
        field.setPadding(dp(14), dp(12), dp(14), dp(12));
        field.setBackground(surface(Color.WHITE, Color.rgb(151, 178, 161)));
        field.setImeOptions(EditorInfo.IME_ACTION_DONE | EditorInfo.IME_FLAG_NO_PERSONALIZED_LEARNING);
        field.setSaveEnabled(false);
        if (Build.VERSION.SDK_INT >= 26) field.setImportantForAutofill(View.IMPORTANT_FOR_AUTOFILL_NO_EXCLUDE_DESCENDANTS);
        row(field, 12);

        local = button("Phân tích trên máy", R.id.run_local);
        style(local, true);
        row(local, 10);
        local.setOnClickListener(v -> runCheck(false));
        field.setOnEditorActionListener((v, action, event) -> {
            if (action != EditorInfo.IME_ACTION_DONE) return false;
            runCheck(false);
            return true;
        });
        result = label(16, false);
        result.setId(R.id.result);
        result.setSaveEnabled(false);
        result.setAccessibilityLiveRegion(View.ACCESSIBILITY_LIVE_REGION_POLITE);
        result.setBackground(surface(Color.WHITE, Color.rgb(203, 219, 206)));
        result.setPadding(dp(16), dp(14), dp(16), dp(14));
        result.setLineSpacing(dp(3), 1);
        row(result, 14);

        online = button("", R.id.run_online);
        style(online, false);
        row(online, 16);
        online.setOnClickListener(v -> runCheck(true));
        networkNotice = label(13, false);
        row(networkNotice, 6);
        field.addTextChangedListener(new TextWatcher() {
            public void beforeTextChanged(CharSequence s, int start, int count, int after) {}
            public void onTextChanged(CharSequence s, int start, int before, int count) { invalidateResult(); }
            public void afterTextChanged(Editable e) {}
        });
        select(true);
    }

    private void select(boolean usePassword) {
        speedMode = false;
        password = usePassword;
        field.setText("");
        local.setText("Phân tích trên máy");
        online.setVisibility(View.VISIBLE);
        field.setInputType(InputType.TYPE_CLASS_TEXT | (password
            ? InputType.TYPE_TEXT_VARIATION_PASSWORD | InputType.TYPE_TEXT_FLAG_NO_SUGGESTIONS
            : InputType.TYPE_TEXT_VARIATION_EMAIL_ADDRESS));
        field.setImeOptions(EditorInfo.IME_ACTION_DONE | EditorInfo.IME_FLAG_NO_PERSONALIZED_LEARNING);
        heading.setText(password ? "Kiểm tra mật khẩu" : "Kiểm tra email");
        instructions.setText(password ? "Nhập mật khẩu để xem độ dài, quy luật lặp và thời gian phân tích."
            : "Kiểm tra cấu trúc địa chỉ, tên miền đăng ký và email tạm.");
        field.setHint(password ? "Mật khẩu" : "Địa chỉ email");
        online.setText(password ? "Kiểm tra rò rỉ" : "Tra DNS tên miền");
        networkNotice.setText(password
            ? "Khi bấm Kiểm tra rò rỉ, ứng dụng gửi 5 ký tự đầu của mã băm SHA-1 đến Pwned Passwords."
            : "Khi bấm Tra DNS, ứng dụng chỉ tra tên miền để đọc bản ghi MX, SPF và DMARC.");
        style(passwordTab, password);
        style(emailTab, !password);
        style(speedTab, false);
        passwordTab.setSelected(password);
        emailTab.setSelected(!password);
        speedTab.setSelected(false);
        invalidateResult();
    }

    private void selectSpeed() {
        speedMode = true;
        password = false;
        field.setText("");
        field.setInputType(InputType.TYPE_CLASS_NUMBER);
        field.setImeOptions(EditorInfo.IME_ACTION_DONE | EditorInfo.IME_FLAG_NO_PERSONALIZED_LEARNING);
        field.setHint("Độ dài cần ước lượng (1–256)");
        heading.setText("Đo tốc độ ngoại tuyến");
        instructions.setText("Duyệt một tập nhỏ chuỗi giả lập ngay trên máy và ước lượng không gian tìm kiếm.");
        local.setText("Đo tốc độ trên máy");
        online.setVisibility(View.GONE);
        networkNotice.setText("Giới hạn 80.000 mẫu bốn ký tự. Không thử mật khẩu hay dịch vụ thật; không gửi dữ liệu.");
        style(passwordTab, false);
        style(emailTab, false);
        style(speedTab, true);
        passwordTab.setSelected(false);
        emailTab.setSelected(false);
        speedTab.setSelected(true);
        invalidateResult();
    }

    private void invalidateResult() {
        revision++;
        if (pending != null) { pending.cancel(true); pending = null; }
        result.setText("");
        result.setVisibility(View.GONE);
        boolean hasInput = field.length() > 0;
        local.setEnabled(hasInput);
        online.setEnabled(hasInput && !speedMode);
    }

    private void runCheck(boolean network) {
        String value = field.getText().toString();
        if (value.isEmpty()) return;
        if (speedMode) {
            try {
                int requestedLength = Integer.parseInt(value);
                if (requestedLength < 1 || requestedLength > 256) throw new NumberFormatException();
            } catch (NumberFormatException e) {
                result.setVisibility(View.VISIBLE);
                result.setText("Nhập độ dài hợp lệ từ 1 đến 256.");
                return;
            }
        }
        if (!speedMode && value.codePointCount(0, value.length()) > (password ? 256 : 512)) {
            result.setVisibility(View.VISIBLE);
            result.setText(password ? "Mật khẩu dài quá 256 ký tự." : "Địa chỉ email quá dài.");
            return;
        }
        ((InputMethodManager)getSystemService(Context.INPUT_METHOD_SERVICE)).hideSoftInputFromWindow(field.getWindowToken(), 0);
        final long ticket = ++revision;
        final String operation = speedMode ? "speed_report" : password
                ? (network ? "breach_report" : "password_report")
                : (network ? "dns_report" : "email_report");
        local.setEnabled(false);
        online.setEnabled(false);
        result.setVisibility(View.VISIBLE);
        result.setText(network ? "Đang tra cứu qua mạng…" : "Đang phân tích trên máy…");
        pending = workers.submit(() -> {
            String output;
            try {
                output = Python.getInstance().getModule("mega_checker.mobile").callAttr(operation, value).toString();
            } catch (RuntimeException e) {
                output = network ? "Chưa xác định được kết quả. Hãy kiểm tra kết nối và thử lại."
                                 : "Không thể phân tích dữ liệu trên thiết bị.";
            }
            final String message = output;
            runOnUiThread(() -> {
                if (ticket != revision || isDestroyed()) return;
                pending = null;
                result.setText(message);
                local.setEnabled(true);
                online.setEnabled(!speedMode);
            });
        });
    }

    @Override protected void onStop() {
        super.onStop();
        field.setText("");
        invalidateResult();
    }
    @Override protected void onDestroy() {
        workers.shutdownNow();
        super.onDestroy();
    }
    private int dp(int v) { return Math.round(v * getResources().getDisplayMetrics().density); }
    private TextView label(int size, boolean bold) {
        TextView v = new TextView(this);
        v.setTextColor(INK);
        v.setTextSize(size);
        v.setTypeface(Typeface.create("sans-serif", bold ? Typeface.BOLD : Typeface.NORMAL));
        return v;
    }
    private Button button(String title, int id) {
        Button v = new Button(this);
        v.setId(id);
        v.setText(title);
        v.setAllCaps(false);
        v.setTextSize(16);
        v.setMinHeight(dp(48));
        return v;
    }
    private GradientDrawable surface(int fill, int stroke) {
        GradientDrawable d = new GradientDrawable();
        d.setColor(fill);
        d.setCornerRadius(dp(12));
        d.setStroke(dp(1), stroke);
        return d;
    }
    private void style(Button v, boolean active) {
        v.setBackgroundTintList(null);
        v.setBackground(surface(active ? TEAL : PALE, active ? TEAL : PALE));
        v.setTextColor(new ColorStateList(new int[][]{new int[]{-android.R.attr.state_enabled}, new int[]{}},
            new int[]{active ? Color.rgb(193, 217, 205) : Color.rgb(100, 122, 111), active ? Color.WHITE : INK}));
    }
    private void row(View v, int gap) {
        LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(-1, -2);
        lp.topMargin = dp(gap);
        page.addView(v, lp);
    }
}
