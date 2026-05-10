import React from 'react';
import {
  AbsoluteFill,
  interpolate,
  spring,
  useCurrentFrame,
  useVideoConfig,
} from 'remotion';

const command =
  "asm score --source openrouter 'cheap LLM under $1 per 1M tokens under 1s'";

const outputLines = [
  'Query: cheap LLM under $1 per 1M tokens under 1s',
  'Taxonomy: ai.llm.chat',
  'Source: OpenRouter ephemeral manifests (364 scoreable / 367 models)',
  'Usage signal: cached OpenRouter ranking snapshot',
  'Caveat: usage is a revealed-preference signal, not benchmark quality.',
  'Warning: OpenRouter does not expose latency; ignored latency constraint.',
  'Hard constraints: representative cost <= $1.0000/1M blended tokens',
  '',
  'Selected: NVIDIA: Nemotron 3 Super (free)',
  'Reason: scored 0.994 via TOPSIS; strongest dimension: cost.',
  '',
  'Ranked services:',
  '1. NVIDIA: Nemotron 3 Super (free)   score=0.9937  cost=$0.0000/1M',
  '2. OpenAI: gpt-oss-120b (free)       score=0.9881  cost=$0.0000/1M',
  '3. MiniMax: MiniMax M2.5 (free)      score=0.9861  cost=$0.0000/1M',
  '4. Google: Gemma 4 31B (free)        score=0.9792  cost=$0.0000/1M',
  '5. Google: Gemma 4 26B A4B (free)    score=0.9758  cost=$0.0000/1M',
  '',
  'Rejected by hard constraints:',
  '- Gemini 3.1 Flash Lite: cost $1.1250/1M > max $1.0000/1M',
  '- GPT Chat Latest: cost $22.5000/1M > max $1.0000/1M',
];

const typeText = (text: string, chars: number) => text.slice(0, Math.max(0, chars));

export const TerminalDemo: React.FC = () => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const intro = spring({frame, fps, config: {damping: 24, stiffness: 110}});
  const titleOpacity = interpolate(frame, [0, 35], [0, 1], {extrapolateRight: 'clamp'});
  const commandChars = Math.floor(interpolate(frame, [80, 180], [0, command.length], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  }));
  const outputCount = Math.floor(interpolate(frame, [205, 660], [0, outputLines.length], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  }));
  const outputScroll = interpolate(frame, [560, 790], [0, -305], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });
  const footerOpacity = interpolate(frame, [690, 760], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});

  return (
    <AbsoluteFill style={styles.page}>
      <div style={{...styles.header, opacity: titleOpacity}}>
        <div>
          <div style={styles.kicker}>Agent Service Manifest</div>
          <div style={styles.title}>Rank live AI services by value metadata</div>
        </div>
        <div style={styles.badge}>OpenRouter demo</div>
      </div>

      <div
        style={{
          ...styles.terminal,
          transform: `translateY(${(1 - intro) * 20}px) scale(${0.985 + intro * 0.015})`,
          opacity: interpolate(frame, [20, 70], [0, 1], {extrapolateRight: 'clamp'}),
        }}
      >
        <div style={styles.windowBar}>
          <span style={{...styles.dot, backgroundColor: '#ff5f56'}} />
          <span style={{...styles.dot, backgroundColor: '#ffbd2e'}} />
          <span style={{...styles.dot, backgroundColor: '#27c93f'}} />
          <span style={styles.path}>~/asm-spec</span>
        </div>
        <div style={styles.body}>
          <div style={styles.prompt}>
            <span style={styles.promptUser}>$</span> {typeText(command, commandChars)}
            {frame >= 80 && frame < 205 ? <span style={styles.cursor}>|</span> : null}
          </div>

          <div style={styles.outputViewport}>
            <div style={{...styles.output, transform: `translateY(${outputScroll}px)`}}>
              {outputLines.slice(0, outputCount).map((line, index) => {
                const isSelected = line.startsWith('Selected:');
                const isRank = /^[1-5]\./.test(line);
                const isWarning = line.startsWith('Warning:') || line.startsWith('Caveat:');
                return (
                  <div
                    key={`${line}-${index}`}
                    style={{
                      ...styles.line,
                      color: isSelected ? '#7ce38b' : isRank ? '#d8e6ff' : isWarning ? '#f5c66f' : '#aeb9cf',
                      fontWeight: isSelected ? 700 : 500,
                    }}
                  >
                    {line || '\u00a0'}
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      </div>

      <div style={{...styles.footer, opacity: footerOpacity}}>
        <span>MCP tells agents what services can do.</span>
        <strong>ASM tells agents what services are worth.</strong>
      </div>
    </AbsoluteFill>
  );
};

const styles: Record<string, React.CSSProperties> = {
  page: {
    background: '#0e1117',
    color: '#eef4ff',
    fontFamily: 'Inter, Arial, sans-serif',
    padding: 56,
  },
  header: {
    display: 'flex',
    alignItems: 'flex-start',
    justifyContent: 'space-between',
    marginBottom: 28,
  },
  kicker: {
    color: '#6ee7b7',
    fontSize: 24,
    fontWeight: 700,
    letterSpacing: 0,
  },
  title: {
    fontSize: 44,
    fontWeight: 760,
    marginTop: 8,
    letterSpacing: 0,
  },
  badge: {
    border: '1px solid #2b3446',
    borderRadius: 6,
    padding: '10px 14px',
    color: '#9fb0c7',
    fontSize: 18,
    background: '#151a23',
  },
  terminal: {
    border: '1px solid #283246',
    borderRadius: 8,
    overflow: 'hidden',
    background: '#101722',
    boxShadow: '0 24px 70px rgba(0, 0, 0, 0.45)',
  },
  windowBar: {
    height: 46,
    background: '#182132',
    display: 'flex',
    alignItems: 'center',
    padding: '0 18px',
    gap: 9,
    borderBottom: '1px solid #283246',
  },
  dot: {
    width: 12,
    height: 12,
    borderRadius: 999,
    display: 'inline-block',
  },
  path: {
    marginLeft: 12,
    color: '#8797b2',
    fontFamily: 'Consolas, Menlo, monospace',
    fontSize: 18,
  },
  body: {
    height: 438,
    padding: '22px 28px',
    fontFamily: 'Consolas, Menlo, monospace',
    fontSize: 21,
    lineHeight: 1.42,
  },
  prompt: {
    color: '#e5ecf8',
    marginBottom: 18,
    whiteSpace: 'pre-wrap',
  },
  promptUser: {
    color: '#6ee7b7',
    fontWeight: 800,
  },
  cursor: {
    color: '#6ee7b7',
    marginLeft: 2,
  },
  output: {
    whiteSpace: 'pre-wrap',
  },
  outputViewport: {
    height: 356,
    overflow: 'hidden',
  },
  line: {
    minHeight: 29,
  },
  footer: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginTop: 28,
    fontSize: 24,
    color: '#9fb0c7',
  },
};
