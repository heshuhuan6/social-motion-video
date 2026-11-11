# 代码与渲染

## 工程与选型

内容与样式分离：content.json 存已核实信息；timeline.json 存 fps、BPM、镜头起止帧、动作落点；组件消费数据。素材与依赖在工程目录。先检查已有 package.json、锁文件、渲染命令、字体，不顺手升级全部依赖。Remotion 相关包版本匹配，新 API 查对应版本官方文档。

- 字卡、图文：HTML/CSS/SVG、Remotion DOM。
- 多元素编排、路径：GSAP，暂停 autoplay 并按帧 seek。
- React 界面：Motion，导出时用可定位到时间的动画状态。
- 三维：Three.js / React Three Fiber，Remotion 可用 ThreeCanvas。
- 大量二维精灵：PixiJS；生成艺术/波形：Canvas / p5.js。
- 数据：D3 / ECharts；已有矢量动效：Lottie / Rive。确认可 seek 和资源已加载。

网页动效导出视频要保证确定性时间、完整素材、固定视口。交互演示录屏才用实时录制。

## 时间基准

运动由帧 f 推导，t=f/fps。不使用 Date.now、随机初始化、CSS 无限计时动画或依赖前一帧的状态累计。粒子固定 seed，三维位置与相机直接算当前帧。

framesPerBeat=fps*60/BPM。30fps 下 150 BPM=12帧，180 BPM=10帧。非整数时第 k 拍使用 round(k*fps*60/BPM)，不要先取整每拍再累计。镜头用半开区间 [startFrame,endFrame)，全片结束帧不渲染。

## 动作

assets/motion-primitives.tsx 提供冲击回弹、节拍包络、切片头像：

- 大字约 5 帧从 0.87 到 1.025，再用 4 帧落到 1，保留稳定阅读。
- 头像三条沿不同方向入场后精确拼回，切片共用原图比例与坐标。
- 超近景拉全景时文字放独立屏幕空间，避免文字缩得读不清。
- 镜头改变方位、俯仰或对象大小，避免每镜同样缓慢绕行。
- 过渡服务切点，遮挡、推镜、形状匹配择其一；落稳后的清晰时间更重要。

## 字体与布局

显式指定中文字体，渲染前等 document.fonts.ready。跨机器优先使用项目内有使用权的字体并记录许可；替代本机字体后重新验排版。随包不含字体。

1080×1920 安全区起点可用左右 75–100px、上下至少 100–160px，按平台 UI 遮挡调整。用文字真实边界，不凭字数猜。长名字优先换行或重排。

## 导出

先验关键帧再渲染，输出 H.264 / yuv420p / 指定 fps，AAC 48kHz。CLI 示意（入口和 ID 以当前工程为准）：

```bash
npx remotion render src/index.ts Intro out/intro-v2.mp4 --codec=h264 --pixel-format=yuv420p --crf=18
```

WebGL 黑屏依次查渲染后端、模型加载、相机裁切、灯光、画布尺寸，再调并发。每轮保留独立视频、分镜、音轨、封面与报告。
