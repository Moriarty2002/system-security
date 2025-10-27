package asymmetric;

import org.bouncycastle.asn1.x500.X500Name;
import org.bouncycastle.asn1.x509.SubjectPublicKeyInfo;
import org.bouncycastle.cert.X509CertificateHolder;
import org.bouncycastle.cert.X509v3CertificateBuilder;
import org.bouncycastle.cert.jcajce.JcaX509CertificateConverter;
import org.bouncycastle.jce.provider.BouncyCastleProvider;
import org.bouncycastle.operator.ContentSigner;
import org.bouncycastle.operator.jcajce.JcaContentSignerBuilder;

import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.math.BigInteger;
import java.nio.charset.StandardCharsets;
import java.security.*;
import java.security.cert.Certificate;
import java.security.cert.X509Certificate;
import java.time.ZonedDateTime;
import java.util.Date;
import javax.crypto.Cipher;

import asymmetric.CertificateGenerator;

public class AsymmetricKeys {

    private static final String CONFIG_DIR = "src/main/resources/asymmetric";
    private static final String KEYSTORE_FILE = "key.pfx";
    private static final char[] KEYSTORE_PSW = !(System.getenv("KEYSTORE_PSW") == null) ? System.getenv("KEYSTORE_PSW").toCharArray() : "keystore_psw".toCharArray();
    private static final String KEYSTORE_ALIAS = "key_alias";
    private static final char[] KEY_PSW= "Unsecure psw".toCharArray();

    // TODO: generate certificate chain
    static void main(String[] args) throws Exception {
        // Register Bouncy Castle provider
        Security.addProvider(new BouncyCastleProvider());

        // 1. Generate KeyPair (RSA 3072 bits – meets JDK 25 stronger requirements)
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
        Certificate cert = CertificateGenerator.generateCertificate(
                "CN=Example, O=MyOrg, L=City, ST=State, C=US",
                "CN=Example, O=MyOrg, L=City, ST=State, C=US",
                keyPair,
                notBefore,
                notAfter,
                "SHA384withRSA"
        );

        // 3. Create/load KeyStore
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

        // 4. Set entry
        ks.setKeyEntry(KEYSTORE_ALIAS, privKey, KEY_PSW, new Certificate[]{cert});

        // 5. Save keystore
        try (FileOutputStream fos = new FileOutputStream(ksFile)) {
            ks.store(fos, KEYSTORE_PSW);
            System.out.println("Keystore stored to " + KEYSTORE_FILE);
        }

        // 6. Retrieve entry
        try (FileInputStream fis = new FileInputStream(ksFile)) {
            KeyStore ks2 = KeyStore.getInstance("PKCS12");
            ks2.load(fis, KEYSTORE_PSW);
            Key key = ks2.getKey(KEYSTORE_ALIAS, KEY_PSW);
            if (!(key instanceof PrivateKey)) {
                throw new IllegalStateException("Expected PrivateKey");
            }
            PrivateKey retrievedPriv = (PrivateKey) key;
            Certificate retrievedCert = ks2.getCertificate(KEYSTORE_ALIAS);
            PublicKey retrievedPub = retrievedCert.getPublicKey();
            System.out.println("Retrieved public key algorithm = " + retrievedPub.getAlgorithm());

            // 7. Use key pair: encrypt with public, decrypt with private (RSA_OAEP with SHA-256)
            String plaintext = "! This is a msg !";
            Cipher encryptCipher = Cipher.getInstance("RSA/ECB/OAEPWithSHA-256AndMGF1Padding");
            encryptCipher.init(Cipher.ENCRYPT_MODE, retrievedPub);
            byte[] cipherBytes = encryptCipher.doFinal(plaintext.getBytes(StandardCharsets.UTF_8));
            System.out.println("Encrypted (base64) = " + java.util.Base64.getEncoder().encodeToString(cipherBytes));

            Cipher decryptCipher = Cipher.getInstance("RSA/ECB/OAEPWithSHA-256AndMGF1Padding");
            decryptCipher.init(Cipher.DECRYPT_MODE, retrievedPriv);
            byte[] decrypted = decryptCipher.doFinal(cipherBytes);
            System.out.println("Decrypted text = " + new String(decrypted, StandardCharsets.UTF_8));
        }
    }
}