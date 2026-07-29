import { useEffect, useRef, useState } from 'react';
import { StatusBar } from 'expo-status-bar';
import * as Speech from 'expo-speech';
import {
  ActivityIndicator,
  KeyboardAvoidingView,
  Platform,
  ScrollView,
  StyleSheet,
  Switch,
  Text,
  TextInput,
  TouchableOpacity,
  View,
} from 'react-native';

import offlineIncidents from './data/incidents.json';
import { buildOfflineBriefText, searchOfflineIncidents } from './lib/offlineSearch';

// expo-speech-recognition requires a custom dev client build (see eas.json) --
// it throws at import time when its native module isn't linked, which is the
// case in plain Expo Go. Load it defensively with require() (catchable, unlike
// a static import) so the rest of the app keeps working in Expo Go until then.
let ExpoSpeechRecognitionModule = null;
let useSpeechRecognitionEvent = () => {};
try {
  const speechRecognition = require('expo-speech-recognition');
  ExpoSpeechRecognitionModule = speechRecognition.ExpoSpeechRecognitionModule;
  useSpeechRecognitionEvent = speechRecognition.useSpeechRecognitionEvent;
} catch {
  // Not available in this environment (e.g. Expo Go) -- mic input stays disabled.
}

const DEFAULT_API_BASE_URL = 'http://192.168.0.163:8000';

// Claude's response is Markdown; strip the syntax so TTS doesn't read out
// symbols like "#" or "**" literally.
const toSpeechText = (markdown) =>
  markdown
    .replace(/^#{1,6}\s*/gm, '')
    .replace(/\*\*(.*?)\*\*/g, '$1')
    .replace(/[*_`]/g, '')
    .replace(/^-{3,}$/gm, '');

export default function App() {
  const [apiBaseUrl, setApiBaseUrl] = useState(DEFAULT_API_BASE_URL);
  const [workDescription, setWorkDescription] = useState('');
  const [facilityType, setFacilityType] = useState('');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState('');
  const [isSpeaking, setIsSpeaking] = useState(false);
  const [offlineMode, setOfflineMode] = useState(false);
  const [isRecording, setIsRecording] = useState(false);
  const [micAvailable, setMicAvailable] = useState(false);
  const latestTranscriptRef = useRef('');
  // Full message history sent to /safety-chat (seeded from /safety-brief's
  // prompt+text once an online briefing comes back). Only available in
  // online mode -- offline mode never talks to Claude, so there's nothing
  // to continue a conversation with.
  const [chatHistory, setChatHistory] = useState([]);
  const [followUpTurns, setFollowUpTurns] = useState([]);
  const [followUpText, setFollowUpText] = useState('');
  const [followUpLoading, setFollowUpLoading] = useState(false);

  useEffect(() => {
    return () => Speech.stop();
  }, []);

  useEffect(() => {
    if (!ExpoSpeechRecognitionModule) {
      setMicAvailable(false);
      return;
    }
    try {
      setMicAvailable(Boolean(ExpoSpeechRecognitionModule.isRecognitionAvailable()));
    } catch {
      setMicAvailable(false);
    }
  }, []);

  useSpeechRecognitionEvent('start', () => {
    latestTranscriptRef.current = '';
    setIsRecording(true);
  });
  useSpeechRecognitionEvent('end', () => {
    setIsRecording(false);
    // Speech ended (silence detected, or the user tapped stop) -- submit
    // automatically instead of requiring a separate button tap.
    const transcript = latestTranscriptRef.current;
    if (transcript.trim()) {
      submitBriefing(transcript);
    }
  });
  useSpeechRecognitionEvent('result', (event) => {
    const transcript = event.results?.[0]?.transcript;
    if (transcript) {
      setWorkDescription(transcript);
      latestTranscriptRef.current = transcript;
    }
  });
  useSpeechRecognitionEvent('error', (event) => {
    setIsRecording(false);
    setError(`音声認識エラー: ${event.error} ${event.message || ''}`.trim());
  });

  const handleMicPress = async () => {
    if (!ExpoSpeechRecognitionModule) return;
    if (isRecording) {
      ExpoSpeechRecognitionModule.stop();
      return;
    }
    try {
      const permission = await ExpoSpeechRecognitionModule.requestPermissionsAsync();
      if (!permission.granted) {
        setError('マイクまたは音声認識の使用が許可されていません');
        return;
      }
      setError('');
      ExpoSpeechRecognitionModule.start({
        lang: 'ja-JP',
        interimResults: true,
        continuous: false,
        // Android's defaults cut recognition off after a very short pause and
        // bias toward short search-query-like phrases, which made anything
        // but a single word get truncated. web_search is Google's recommended
        // fix for that bias; the two silence-length extras give the user a
        // couple of seconds to keep talking before recognition ends.
        ...(Platform.OS === 'android' && {
          androidIntentOptions: {
            EXTRA_LANGUAGE_MODEL: 'web_search',
            EXTRA_SPEECH_INPUT_COMPLETE_SILENCE_LENGTH_MILLIS: 2500,
            EXTRA_SPEECH_INPUT_POSSIBLY_COMPLETE_SILENCE_LENGTH_MILLIS: 2500,
            EXTRA_SPEECH_INPUT_MINIMUM_LENGTH_MILLIS: 15000,
          },
        }),
      });
    } catch (err) {
      setError(`音声認識を開始できませんでした: ${err.message}`);
    }
  };

  const runOffline = (description) => {
    const matches = searchOfflineIncidents(description, offlineIncidents, 5);
    setResult({
      text: buildOfflineBriefText(description, matches),
      incident_count: matches.length,
      incidents: matches.map((m) => ({
        date: m.date,
        description: m.description,
        severity: m.severity,
      })),
    });
  };

  const runOnline = async (description) => {
    const response = await fetch(`${apiBaseUrl}/safety-brief`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        work_description: description,
        facility_type: facilityType || undefined,
      }),
    });
    const body = await response.json();
    if (!response.ok) {
      setError(`エラー (${response.status}): ${body.detail || JSON.stringify(body)}`);
    } else {
      setResult(body);
      // Seed the chat history with the exact prompt Claude was given (incidents
      // + work description) so follow-up questions have the same context.
      setChatHistory([
        { role: 'user', content: body.prompt },
        { role: 'assistant', content: body.text },
      ]);
    }
  };

  const handleFollowUp = async () => {
    const question = followUpText.trim();
    if (!question) return;
    setFollowUpLoading(true);
    setError('');
    try {
      const response = await fetch(`${apiBaseUrl}/safety-chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ history: chatHistory, message: question }),
      });
      const body = await response.json();
      if (!response.ok) {
        setError(`エラー (${response.status}): ${body.detail || JSON.stringify(body)}`);
      } else {
        setChatHistory(body.history);
        setFollowUpTurns((prev) => [...prev, { question, answer: body.reply }]);
        setFollowUpText('');
      }
    } catch (err) {
      setError(`通信エラー: ${err.message}`);
    } finally {
      setFollowUpLoading(false);
    }
  };

  // Takes an explicit description rather than reading `workDescription` from
  // closure -- called right after setWorkDescription() from the speech "end"
  // event, where the state update hasn't necessarily flushed yet.
  const submitBriefing = async (description) => {
    if (!description.trim()) {
      setError('作業内容を入力してください');
      return;
    }
    Speech.stop();
    setIsSpeaking(false);
    setLoading(true);
    setError('');
    setResult(null);
    setChatHistory([]);
    setFollowUpTurns([]);
    setFollowUpText('');
    try {
      if (offlineMode) {
        runOffline(description);
      } else {
        await runOnline(description);
      }
    } catch (err) {
      setError(`通信エラー: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = () => submitBriefing(workDescription);

  const handleToggleSpeak = () => {
    if (isSpeaking) {
      Speech.stop();
      setIsSpeaking(false);
      return;
    }
    setIsSpeaking(true);
    Speech.speak(toSpeechText(result.text), {
      language: 'ja-JP',
      onDone: () => setIsSpeaking(false),
      onStopped: () => setIsSpeaking(false),
      onError: () => setIsSpeaking(false),
    });
  };

  return (
    <KeyboardAvoidingView
      style={styles.flex}
      behavior={Platform.OS === 'ios' ? 'padding' : undefined}
    >
      <ScrollView contentContainerStyle={styles.container} keyboardShouldPersistTaps="handled">
        <StatusBar style="auto" />
        <Text style={styles.title}>労働災害防止 安全ブリーフィング</Text>

        <View style={styles.offlineRow}>
          <View style={styles.offlineLabelBlock}>
            <Text style={styles.label}>オフラインモード（サーバー不要）</Text>
            <Text style={styles.offlineHint}>
              {offlineMode
                ? 'スマホ内蔵の84件の事例から検索します（Claudeによる生成なし）'
                : 'バックエンドに接続してClaudeが安全ブリーフィングを生成します'}
            </Text>
          </View>
          <Switch value={offlineMode} onValueChange={setOfflineMode} />
        </View>

        {!offlineMode && (
          <>
            <Text style={styles.label}>バックエンドURL</Text>
            <TextInput
              style={styles.input}
              value={apiBaseUrl}
              onChangeText={setApiBaseUrl}
              autoCapitalize="none"
              autoCorrect={false}
              placeholder="http://192.168.x.x:8000"
            />
          </>
        )}

        <View style={styles.workDescriptionLabelRow}>
          <Text style={styles.label}>作業内容</Text>
          <TouchableOpacity
            style={[styles.micButton, !micAvailable && styles.micButtonDisabled]}
            onPress={handleMicPress}
            disabled={!micAvailable}
          >
            <Text
              style={[styles.micButtonText, !micAvailable && styles.micButtonTextDisabled]}
            >
              {isRecording ? '⏹ 停止' : '🎤 音声入力'}
            </Text>
          </TouchableOpacity>
        </View>
        {!micAvailable && (
          <Text style={styles.offlineHint}>
            マイク入力はこの環境（Expo Go）では使用できません。カスタム開発ビルドが必要です。
          </Text>
        )}
        <TextInput
          style={[styles.input, styles.multiline]}
          value={workDescription}
          onChangeText={setWorkDescription}
          placeholder="例: 足場の組立で高さ5mの作業"
          multiline
        />

        <Text style={styles.label}>施設種別（任意）</Text>
        <TextInput
          style={styles.input}
          value={facilityType}
          onChangeText={setFacilityType}
          placeholder="例: 建設現場"
        />

        <TouchableOpacity style={styles.button} onPress={handleSubmit} disabled={loading}>
          {loading ? (
            <ActivityIndicator color="#fff" />
          ) : (
            <Text style={styles.buttonText}>安全ブリーフィングを取得</Text>
          )}
        </TouchableOpacity>

        {error ? <Text style={styles.error}>{error}</Text> : null}

        {result ? (
          <View style={styles.resultBox}>
            <View style={styles.resultTitleRow}>
              <Text style={styles.resultTitle}>安全ブリーフィング</Text>
              <TouchableOpacity style={styles.speakButton} onPress={handleToggleSpeak}>
                <Text style={styles.speakButtonText}>
                  {isSpeaking ? '⏹ 停止' : '🔊 音声で聴く'}
                </Text>
              </TouchableOpacity>
            </View>
            <Text style={styles.resultText}>{result.text}</Text>

            <Text style={styles.resultTitle}>類似災害事例（{result.incident_count}件）</Text>
            {result.incidents.map((incident, index) => (
              <View key={index} style={styles.incidentRow}>
                <Text style={styles.incidentText}>
                  {incident.date} ・ 重大度: {incident.severity}
                </Text>
                <Text style={styles.incidentText}>{incident.description}</Text>
              </View>
            ))}

            {!offlineMode && chatHistory.length > 0 && (
              <View style={styles.followUpSection}>
                <Text style={styles.resultTitle}>追加で質問する</Text>
                {followUpTurns.map((turn, index) => (
                  <View key={index} style={styles.followUpTurn}>
                    <Text style={styles.followUpQuestion}>Q. {turn.question}</Text>
                    <Text style={styles.followUpAnswer}>{turn.answer}</Text>
                  </View>
                ))}
                <TextInput
                  style={styles.input}
                  value={followUpText}
                  onChangeText={setFollowUpText}
                  placeholder="例: 保護具は何が必要ですか？"
                />
                <TouchableOpacity
                  style={styles.button}
                  onPress={handleFollowUp}
                  disabled={followUpLoading}
                >
                  {followUpLoading ? (
                    <ActivityIndicator color="#fff" />
                  ) : (
                    <Text style={styles.buttonText}>質問する</Text>
                  )}
                </TouchableOpacity>
              </View>
            )}
          </View>
        ) : null}
      </ScrollView>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  flex: { flex: 1 },
  container: {
    flexGrow: 1,
    backgroundColor: '#fff',
    padding: 20,
    paddingTop: 60,
  },
  title: {
    fontSize: 20,
    fontWeight: 'bold',
    marginBottom: 20,
  },
  label: {
    fontSize: 14,
    fontWeight: '600',
    marginTop: 12,
    marginBottom: 4,
  },
  offlineRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    backgroundColor: '#f7f7f9',
    borderRadius: 8,
    padding: 12,
    marginTop: 8,
  },
  offlineLabelBlock: {
    flex: 1,
    marginRight: 12,
  },
  offlineHint: {
    fontSize: 12,
    color: '#666',
    marginTop: 2,
  },
  input: {
    borderWidth: 1,
    borderColor: '#ccc',
    borderRadius: 8,
    padding: 10,
    fontSize: 16,
  },
  multiline: {
    minHeight: 80,
    textAlignVertical: 'top',
  },
  button: {
    backgroundColor: '#1e6fd9',
    borderRadius: 8,
    padding: 14,
    alignItems: 'center',
    marginTop: 20,
  },
  buttonText: {
    color: '#fff',
    fontSize: 16,
    fontWeight: '600',
  },
  error: {
    color: '#c0392b',
    marginTop: 16,
  },
  resultBox: {
    marginTop: 24,
    borderTopWidth: 1,
    borderTopColor: '#eee',
    paddingTop: 16,
  },
  resultTitle: {
    fontSize: 16,
    fontWeight: 'bold',
    marginTop: 12,
    marginBottom: 6,
  },
  resultTitleRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  speakButton: {
    backgroundColor: '#eef4ff',
    borderRadius: 6,
    paddingVertical: 6,
    paddingHorizontal: 10,
  },
  speakButtonText: {
    color: '#1e6fd9',
    fontSize: 13,
    fontWeight: '600',
  },
  workDescriptionLabelRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginTop: 12,
  },
  micButton: {
    backgroundColor: '#eef4ff',
    borderRadius: 6,
    paddingVertical: 6,
    paddingHorizontal: 10,
  },
  micButtonDisabled: {
    backgroundColor: '#f0f0f0',
  },
  micButtonText: {
    color: '#1e6fd9',
    fontSize: 13,
    fontWeight: '600',
  },
  micButtonTextDisabled: {
    color: '#999',
  },
  resultText: {
    fontSize: 15,
    lineHeight: 22,
  },
  incidentRow: {
    marginBottom: 10,
    paddingBottom: 10,
    borderBottomWidth: 1,
    borderBottomColor: '#f0f0f0',
  },
  incidentText: {
    fontSize: 13,
    color: '#333',
  },
  followUpSection: {
    marginTop: 20,
    borderTopWidth: 1,
    borderTopColor: '#eee',
    paddingTop: 16,
  },
  followUpTurn: {
    marginBottom: 12,
  },
  followUpQuestion: {
    fontSize: 14,
    fontWeight: '600',
    marginBottom: 4,
  },
  followUpAnswer: {
    fontSize: 14,
    lineHeight: 20,
    color: '#333',
  },
});
