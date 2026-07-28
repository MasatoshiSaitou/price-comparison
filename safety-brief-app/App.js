import { useState } from 'react';
import { StatusBar } from 'expo-status-bar';
import {
  ActivityIndicator,
  KeyboardAvoidingView,
  Platform,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  TouchableOpacity,
  View,
} from 'react-native';

const DEFAULT_API_BASE_URL = 'http://192.168.0.163:8000';

export default function App() {
  const [apiBaseUrl, setApiBaseUrl] = useState(DEFAULT_API_BASE_URL);
  const [workDescription, setWorkDescription] = useState('');
  const [facilityType, setFacilityType] = useState('');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState('');

  const handleSubmit = async () => {
    if (!workDescription.trim()) {
      setError('作業内容を入力してください');
      return;
    }
    setLoading(true);
    setError('');
    setResult(null);
    try {
      const response = await fetch(`${apiBaseUrl}/safety-brief`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          work_description: workDescription,
          facility_type: facilityType || undefined,
        }),
      });
      const body = await response.json();
      if (!response.ok) {
        setError(`エラー (${response.status}): ${body.detail || JSON.stringify(body)}`);
      } else {
        setResult(body);
      }
    } catch (err) {
      setError(`通信エラー: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  return (
    <KeyboardAvoidingView
      style={styles.flex}
      behavior={Platform.OS === 'ios' ? 'padding' : undefined}
    >
      <ScrollView contentContainerStyle={styles.container} keyboardShouldPersistTaps="handled">
        <StatusBar style="auto" />
        <Text style={styles.title}>労働災害防止 安全ブリーフィング</Text>

        <Text style={styles.label}>バックエンドURL</Text>
        <TextInput
          style={styles.input}
          value={apiBaseUrl}
          onChangeText={setApiBaseUrl}
          autoCapitalize="none"
          autoCorrect={false}
          placeholder="http://192.168.x.x:8000"
        />

        <Text style={styles.label}>作業内容</Text>
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
            <Text style={styles.resultTitle}>安全ブリーフィング</Text>
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
});
