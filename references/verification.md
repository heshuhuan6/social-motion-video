# 验收与交付

```bash
python3 /path/to/social-motion-video/scripts/check-video.py out/intro-v2.mp4 --width 1080 --height 1920 --fps 30 --duration 20 --cover-time 18.6 --out-dir out/qa-v2
```

脚本核规格、完整解码每帧、筛疑似纯色帧、测 AAC 响度、抽封面，输出 specs.json、frame-check.json、audio-check.json、summary.json、cover.jpg。非零退出表示失败或需复核。合法纯色转场人工确认后在说明注明帧号，不降阈值掩盖异常。

## 几何与目视

像素统计只筛空白。文字溢出和错位另做布局检查与目视复核：

- 关键文字稳定 ID，每帧采集实际 DOM 几何；等待字体和素材，用根画布尺寸还原成片坐标。
- 可见文字边界是否越过安全区；scrollWidth/scrollHeight 是否大于 clientWidth/clientHeight。
- 独立文字区意外重叠；父子嵌套、设计叠字明确白名单。
- 入出场设计越界记录允许帧段，稳定阅读阶段严格检查。
- 报告唯一帧号覆盖 0..durationInFrames-1，重复日志不重复计数。真正覆盖才报告逐帧布局通过。

Canvas 内文字、透视、遮挡与颜色对比需要目视。生成逐秒联系表、前三秒每秒至少 5 张、所有转场前后帧。原尺寸检查首帧、最密文字、末屏、字体替代、拉伸、模型穿帮。

## 声音与版本

复核每句落点、尾音、静音间隙与压低恢复；最终编码后测 LUFS 与真峰值。只加口播时对照视频流 hash：

```bash
ffmpeg -v error -i out/intro-v1.mp4 -map 0:v:0 -c copy -f hash -hash sha256 -
ffmpeg -v error -i out/intro-v2.mp4 -map 0:v:0 -c copy -f hash -hash sha256 -
```

验收后复制版本视频、封面到主路径。说明记录创意、事实、分镜、复现命令、实际验证结果和已知不足，区分自动检测、目视、听审的完成范围。
