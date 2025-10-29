package asymmetric.sign;

import org.bouncycastle.asn1.pkcs.PKCSObjectIdentifiers;
import org.bouncycastle.asn1.pkcs.PrivateKeyInfo;
import org.bouncycastle.jce.provider.BouncyCastleProvider;

import java.io.*;
import java.security.*;
import javax.security.auth.x500.X500Principal;

import org.bouncycastle.openssl.*;
import org.bouncycastle.openssl.jcajce.*;
import org.bouncycastle.operator.ContentSigner;
import org.bouncycastle.operator.InputDecryptorProvider;
import org.bouncycastle.operator.OutputEncryptor;
import org.bouncycastle.operator.jcajce.JcaContentSignerBuilder;
import org.bouncycastle.pkcs.PKCS10CertificationRequest;
import org.bouncycastle.pkcs.PKCS10CertificationRequestBuilder;
import org.bouncycastle.pkcs.PKCS8EncryptedPrivateKeyInfo;
import org.bouncycastle.pkcs.jcajce.JcaPKCS10CertificationRequestBuilder;

public class AsymmetricKeysUser {

    private final String CONFIG_DIR = "src/main/resources/asymmetric/";
    private final String PRIVATE_KEY_NAME = "private_key_user.pem";
    private final String PUBLIC_KEY_NAME = "public_key_user.pem";
    private final String KEY_PSW= "Unsecure psw";
    private final String USER_DN_NAME = "CN=www.unina.it, OU=Dipartimento di Elettronica e Informatica, O=Università degli studi di Napoli Federico II, L=Napoli, ST=NA, C=IT";
    private final String ALGORITHM = "SHA256withRSA";

    AsymmetricKeysUser() {
        try {
            // Register Bouncy Castle provider
            Security.addProvider(new BouncyCastleProvider());

            // generate KeyPair (RSA 3072 bits key)
            KeyPairGenerator kpg = KeyPairGenerator.getInstance("RSA");
            kpg.initialize(3072);
            KeyPair keyPair = kpg.generateKeyPair();

            saveEncryptedKeyPEM(keyPair, CONFIG_DIR, KEY_PSW);
        } catch (Exception e) {
            throw new RuntimeException(e);
        }
    }


    public PKCS10CertificationRequest generateCSR() {
        try {
            KeyPair keyPair = loadEncryptedKeyPEM(CONFIG_DIR, KEY_PSW);

            // Build CSR
            PKCS10CertificationRequestBuilder p10Builder =
                    new JcaPKCS10CertificationRequestBuilder(
                            new X500Principal(USER_DN_NAME),
                            keyPair.getPublic()
                    );

            JcaContentSignerBuilder csBuilder =
                    new JcaContentSignerBuilder(ALGORITHM)
                            .setProvider("BC");
            ContentSigner signer = csBuilder.build(keyPair.getPrivate());

            return p10Builder.build(signer);
        } catch (Exception e) {
            throw new RuntimeException(e);
        }
    }

    public void saveEncryptedKeyPEM(KeyPair keyPair, String filePath, String password) throws Exception {
        Security.addProvider(new BouncyCastleProvider());

        // --- Write encrypted private key (PKCS#8 with AES-256-CBC) ---
        try (Writer writer = new FileWriter(filePath + PRIVATE_KEY_NAME);
             JcaPEMWriter pemWriter = new JcaPEMWriter(writer)) {

            // ✅ Use ASN1ObjectIdentifier instead of String
            OutputEncryptor encryptor = new JceOpenSSLPKCS8EncryptorBuilder(
                    PKCSObjectIdentifiers.pbeWithSHAAnd3_KeyTripleDES_CBC // or AES-256 equivalent below
            )
                    .setProvider("BC")
                    .setRandom(new SecureRandom())
                    .setPassword(password.toCharArray())
                    .build();

            // Or, for AES-256, you can use this OID:
            // PKCSObjectIdentifiers.id_PBES2  (recommended modern one)

            JcaPKCS8Generator pkcs8Generator = new JcaPKCS8Generator(keyPair.getPrivate(), encryptor);
            pemWriter.writeObject(pkcs8Generator);
        }

        // --- Write public key ---
        try (Writer writer = new FileWriter(filePath + PUBLIC_KEY_NAME);
             JcaPEMWriter pemWriter = new JcaPEMWriter(writer)) {
            pemWriter.writeObject(keyPair.getPublic());
        }
    }

    private KeyPair loadEncryptedKeyPEM(String filePath, String password) throws Exception {
        Security.addProvider(new BouncyCastleProvider());

        PrivateKey privateKey;
        PublicKey publicKey;
        File privFile = new File(filePath + PRIVATE_KEY_NAME);
        if (!privFile.exists() || privFile.length() == 0) {
            throw new FileNotFoundException("Private key file not found or empty: " + privFile.getAbsolutePath());
        }

        // --- Load and decrypt private key ---
        try (PEMParser parser = new PEMParser(new FileReader(filePath + PRIVATE_KEY_NAME))) {
            Object obj = parser.readObject();

            if (!(obj instanceof PKCS8EncryptedPrivateKeyInfo encryptedInfo)) {
                throw new IllegalStateException("Expected PKCS8EncryptedPrivateKeyInfo, got: " + obj.getClass());
            }

            // Build decryptor
            InputDecryptorProvider decryptorProvider =
                    new JceOpenSSLPKCS8DecryptorProviderBuilder()
                            .setProvider("BC")
                            .build(password.toCharArray());

            // Decrypt to get PrivateKeyInfo
            PrivateKeyInfo privateKeyInfo = encryptedInfo.decryptPrivateKeyInfo(decryptorProvider);

            // Convert to standard PrivateKey
            privateKey = new JcaPEMKeyConverter()
                    .setProvider("BC")
                    .getPrivateKey(privateKeyInfo);
        }

        // --- Load public key ---
        try (PEMParser parser = new PEMParser(new FileReader(filePath + PUBLIC_KEY_NAME))) {
            Object obj = parser.readObject();

            publicKey = new JcaPEMKeyConverter()
                    .setProvider("BC")
                    .getPublicKey(
                            org.bouncycastle.asn1.x509.SubjectPublicKeyInfo.getInstance(obj)
                    );
        }

        return new KeyPair(publicKey, privateKey);
    }
 }