package asymmetric.sign;

import asymmetric.CertificateGenerator;
import org.bouncycastle.jce.provider.BouncyCastleProvider;
import org.bouncycastle.pkcs.PKCS10CertificationRequest;

import javax.crypto.Cipher;
import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.nio.charset.StandardCharsets;
import java.security.*;
import java.security.cert.Certificate;
import java.security.cert.X509Certificate;
import java.time.ZonedDateTime;
import java.util.Date;

public class AsymmetricKeysCA {

    private final String CONFIG_DIR = "src/main/resources/asymmetric";
    private final String KEYSTORE_FILE = "key_store_CA.pfx";
    private final char[] KEYSTORE_PSW = !(System.getenv("KEYSTORE_PSW") == null) ? System.getenv("KEYSTORE_PSW").toCharArray() : "keystore_psw".toCharArray();
    private final String KEYSTORE_ALIAS = "key_alias";
    private final char[] KEY_PSW= "Unsecure psw".toCharArray();
    private final String CA_DN_NAME = "CN=Poste Italiane CA Servizi Qualificati, OU=Servizi di Certificazione, O=Poste Italiane S.p.A., L=Roma, ST=RM, C=IT";

    AsymmetricKeysCA(){
        try {
            // Register Bouncy Castle provider
            Security.addProvider(new BouncyCastleProvider());

            // generate KeyPair (RSA 3072 bits key)
            KeyPairGenerator kpg = KeyPairGenerator.getInstance("RSA");
            kpg.initialize(3072);
            KeyPair keyPair = kpg.generateKeyPair();
            PublicKey pubKey = keyPair.getPublic();
            PrivateKey privKey = keyPair.getPrivate();
            System.out.println("Generated key pair algorithm = " + pubKey.getAlgorithm());

            // 2. Create self-signed X509Certificate (valid 1 year)
            long days = 365;
            Date notBefore = Date.from(ZonedDateTime.now().toInstant());
            Date notAfter = Date.from(ZonedDateTime.now().plusDays(days).toInstant());
            Certificate cert = CertificateGenerator.generateCertificateSelfSigned (
                    CA_DN_NAME,
                    keyPair,
                    notBefore,
                    notAfter,
                    "SHA384withRSA"
            );


            KeyStore ks = KeyStore.getInstance("PKCS12");
            File ksFile = new File(CONFIG_DIR, KEYSTORE_FILE);
            if (ksFile.exists()) {
                try (FileInputStream fis = new FileInputStream(ksFile)) {
                    ks.load(fis, KEYSTORE_PSW);
                    System.out.println("Loaded existing keystore.");
                }
            } else {
                ks.load(null, null);
                System.out.println("Created new keystore.");
            }

            ks.setKeyEntry(KEYSTORE_ALIAS, privKey, KEY_PSW, new Certificate[]{cert});

            try (FileOutputStream fos = new FileOutputStream(ksFile)) {
                ks.store(fos, KEYSTORE_PSW);
                System.out.println("Keystore stored to " + KEYSTORE_FILE);
            }
        } catch (Exception e) {
            throw new RuntimeException(e);
        }
    }

    public X509Certificate signCertificate(PKCS10CertificationRequest csr) {
        File ksFile = new File(CONFIG_DIR, KEYSTORE_FILE);
        try (FileInputStream fis = new FileInputStream(ksFile)) {
            KeyStore ks = KeyStore.getInstance("PKCS12");
            ks.load(fis, KEYSTORE_PSW);
            Key key = ks.getKey(KEYSTORE_ALIAS, KEY_PSW);
            PrivateKey privKey = (PrivateKey) key;

            return CertificateGenerator.signCSR(
                    csr, 
                    CA_DN_NAME,
                    privKey,
                    Date.from(ZonedDateTime.now().toInstant()),
                    Date.from(ZonedDateTime.now().plusDays(365).toInstant()),
                    "SHA384withRSA"
                    );
        } catch (Exception e) {
            throw new RuntimeException(e);
        }
    }
}