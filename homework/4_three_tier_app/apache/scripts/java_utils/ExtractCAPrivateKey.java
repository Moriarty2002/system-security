import java.io.*;
import java.security.*;
import java.security.cert.Certificate;

public class ExtractCAPrivateKey {
    
    public static void main(String[] args) {
        String keystorePath = "/shared/University/system_security/system-security/homework/2_JavaCryptographyArchitecture/java_crypthography_architecture/src/main/resources/asymmetric/key_store_CA.pfx";
        String keystorePassword = "keystore_psw";
        String keyPassword = "Unsecure psw";
        String alias = "key_alias";
        String outputKeyFile = "/shared/University/system_security/system-security/homework/4_three_tier_app/apache/certs/CA_private_key.pem";
        String outputCertFile = "/shared/University/system_security/system-security/homework/4_three_tier_app/apache/certs/CA_cert_from_keystore.pem";
        String outputBundleFile = "/shared/University/system_security/system-security/homework/4_three_tier_app/apache/certs/CA_bundle.pem";
        
        try {
            // Load the keystore
            KeyStore keyStore = KeyStore.getInstance("PKCS12");
            try (FileInputStream fis = new FileInputStream(keystorePath)) {
                keyStore.load(fis, keystorePassword.toCharArray());
            }
            
            System.out.println("Keystore loaded successfully!");
            
            // Get the private key
            Key key = keyStore.getKey(alias, keyPassword.toCharArray());
            if (key instanceof PrivateKey) {
                PrivateKey privateKey = (PrivateKey) key;
                System.out.println("Private key retrieved!");
                System.out.println("Algorithm: " + privateKey.getAlgorithm());
                System.out.println("Format: " + privateKey.getFormat());
                
                // Get the certificate
                Certificate cert = keyStore.getCertificate(alias);
                System.out.println("Certificate retrieved!");
                
                // Write private key to PEM file
                writePrivateKeyToPEM(privateKey, outputKeyFile);
                System.out.println("Private key written to: " + outputKeyFile);
                
                // Write certificate to PEM file
                writeCertificateToPEM(cert, outputCertFile);
                System.out.println("Certificate written to: " + outputCertFile);
                
                // Write bundle (private key + certificate)
                writeBundle(privateKey, cert, outputBundleFile);
                System.out.println("Bundle written to: " + outputBundleFile);
                
            } else {
                System.err.println("Key is not a PrivateKey!");
            }
            
        } catch (Exception e) {
            System.err.println("Error: " + e.getMessage());
            e.printStackTrace();
        }
    }
    
    private static void writePrivateKeyToPEM(PrivateKey privateKey, String filename) throws IOException {
        try (FileWriter fw = new FileWriter(filename);
             BufferedWriter bw = new BufferedWriter(fw)) {
            
            bw.write("-----BEGIN PRIVATE KEY-----\n");
            
            // Get the encoded key and convert to Base64
            byte[] encoded = privateKey.getEncoded();
            String base64 = java.util.Base64.getEncoder().encodeToString(encoded);
            
            // Write in 64-character lines
            for (int i = 0; i < base64.length(); i += 64) {
                int end = Math.min(i + 64, base64.length());
                bw.write(base64.substring(i, end) + "\n");
            }
            
            bw.write("-----END PRIVATE KEY-----\n");
        }
    }
    
    private static void writeCertificateToPEM(Certificate cert, String filename) throws Exception {
        try (FileWriter fw = new FileWriter(filename);
             BufferedWriter bw = new BufferedWriter(fw)) {
            
            bw.write("-----BEGIN CERTIFICATE-----\n");
            
            // Get the encoded certificate and convert to Base64
            byte[] encoded = cert.getEncoded();
            String base64 = java.util.Base64.getEncoder().encodeToString(encoded);
            
            // Write in 64-character lines
            for (int i = 0; i < base64.length(); i += 64) {
                int end = Math.min(i + 64, base64.length());
                bw.write(base64.substring(i, end) + "\n");
            }
            
            bw.write("-----END CERTIFICATE-----\n");
        }
    }
    
    private static void writeBundle(PrivateKey privateKey, Certificate cert, String filename) throws Exception {
        try (FileWriter fw = new FileWriter(filename);
             BufferedWriter bw = new BufferedWriter(fw)) {
            
            // Write private key
            bw.write("-----BEGIN PRIVATE KEY-----\n");
            byte[] keyEncoded = privateKey.getEncoded();
            String keyBase64 = java.util.Base64.getEncoder().encodeToString(keyEncoded);
            for (int i = 0; i < keyBase64.length(); i += 64) {
                int end = Math.min(i + 64, keyBase64.length());
                bw.write(keyBase64.substring(i, end) + "\n");
            }
            bw.write("-----END PRIVATE KEY-----\n");
            
            // Write certificate
            bw.write("-----BEGIN CERTIFICATE-----\n");
            byte[] certEncoded = cert.getEncoded();
            String certBase64 = java.util.Base64.getEncoder().encodeToString(certEncoded);
            for (int i = 0; i < certBase64.length(); i += 64) {
                int end = Math.min(i + 64, certBase64.length());
                bw.write(certBase64.substring(i, end) + "\n");
            }
            bw.write("-----END CERTIFICATE-----\n");
        }
    }
}
