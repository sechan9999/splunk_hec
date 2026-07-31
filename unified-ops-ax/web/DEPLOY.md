# Unified Ops AX 대시보드 배포

`index.html`은 **완전 자체완결 정적 대시보드**(백엔드·외부 CDN 없음)이므로 어디든 그대로 올라갑니다. 계정 로그인·배포 실행은 본인 계정에서 진행하세요.

## A. Vercel (정적, 권장)

### A-1. CLI (가장 빠름)
```bash
cd unified-ops-ax/web
npx vercel --prod        # 최초 1회 로그인(브라우저) 후 URL 발급
```

### A-2. GitHub 연동 (자동 배포)
1. vercel.com → Add New → Project → `sechan9999/splunk_hec` 임포트
2. **Root Directory** = `unified-ops-ax/web`
3. Framework Preset = **Other** (빌드 없음), Deploy → `https://<프로젝트>.vercel.app`
4. 이후 master push마다 자동 재배포

## B. Streamlit Community Cloud

`streamlit_dashboard.py`가 이 정적 HTML을 감싸 렌더합니다.
1. share.streamlit.io → New app
2. Repository = `sechan9999/splunk_hec`, Branch = `master`
3. **Main file path** = `unified-ops-ax/web/streamlit_dashboard.py`
4. Deploy → `https://<앱>.streamlit.app`

로컬 확인:
```bash
cd unified-ops-ax/web
pip install -r requirements.txt
streamlit run streamlit_dashboard.py
```

## C. 그 외 (계정 불필요/간단)
- **GitHub Pages**: repo Settings → Pages → 이 폴더 지정 (또는 정적 호스팅)
- **Netlify**: 폴더 드래그&드롭

---
현재 대시보드는 데모 데이터(15/15, 정합 100% 등)를 담은 **정적 스냅샷**입니다. 실시간 백엔드 연동판(`../unified_ops_ax_dashboard.html`)은 FastAPI 서버가 필요하며 정적 호스팅 단독으로는 동적 부분이 동작하지 않습니다.
