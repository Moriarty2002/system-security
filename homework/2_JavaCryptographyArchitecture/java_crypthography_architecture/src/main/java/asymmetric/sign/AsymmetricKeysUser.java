package asymmetric.sign;

import org.bouncycastle.asn1.pkcs.PrivateKeyInfo;
import org.bouncycastle.jce.provider.BouncyCastleProvider;

import java.io.*;
import java.nio.charset.StandardCharsets;
import java.security.*;
import java.security.cert.Certificate;
import java.time.ZonedDateTime;
import java.util.Date;
import javax.crypto.Cipher;

import asymmetric.CertificateGenerator;
import org.bouncycastle.openssl.*;
import org.bouncycastle.openssl.jcajce.JcaPEMKeyConverter;
import org.bouncycastle.openssl.jcajce.JcaPEMWriter;
import org.bouncycastle.openssl.jcajce.JcePEMDecryptorProviderBuilder;
import org.bouncycastle.openssl.jcajce.JcePEMEncryptorBuilder;
import org.bouncycastle.pkcs.PKCS10CertificationRequest;

public class AsymmetricKeysUser {

    private final String CONFIG_DIR = "src/main/resources/asymmetric";
    private final String KEYSTORE_FILE = "key_store_user.pfx";
    private final char[] KEYSTORE_PSW = !(System.getenv("KEYSTORE_PSW") == null) ? System.getenv("KEYSTORE_PSW").toCharArray() : "keystore_psw".toCharArray();
    private final String KEYSTORE_ALIAS = "key_alias";
    private final String KEY_PSW= "Unsecure psw";
    private final String USER_DN_NAME = "CN=www.unina.it, OU=Dipartimento di Elettronica e Informatica, O=Università degli studi di Napoli Federico II, L=Napoli, ST=NA, C=IT";

    // TODO: user have to request a CSR

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
        } catch (Exception e) {
            throw new RuntimeException(e);
        }

        return null;
    }

    private void saveEncryptedKeyPEM(KeyPair keyPair, String filePath, String password) throws Exception {
        try (JcaPEMWriter pemWriter = new JcaPEMWriter(new FileWriter(filePath + "/private_key_user.pem"))) {
            PEMEncryptor encryptor = new JcePEMEncryptorBuilder("AES-256-CBC")
                    .setProvider("BC")
                    .build(password.toCharArray());
            pemWriter.writeObject(new MiscPEMGenerator(keyPair.getPrivate(), encryptor));
        }

        try (JcaPEMWriter pemWriter = new JcaPEMWriter(new FileWriter(filePath + "/public_key_user.pem"))) {
            pemWriter.writeObject(keyPair.getPublic());
        }
    }

    private KeyPair loadEncryptedKeyPEM(String filePath, String password) throws Exception {
        PrivateKey privateKey = null;
        PublicKey publicKey = null;

        try (PEMParser parser = new PEMParser(new FileReader(filePath))) {
            PrivateKeyInfo privateKeyInfo = (PrivateKeyInfo) parser.readObject();
            JcaPEMKeyConverter converter = new JcaPEMKeyConverter().setProvider("BC");
            privateKey = converter.getPrivateKey(privateKeyInfo);
        }

        try (PEMParser parser = new PEMParser(new FileReader(filePath))) {
            Object object = parser.readObject();
            publicKey = new JcaPEMKeyConverter().getPublicKey(
                    org.bouncycastle.asn1.x509.SubjectPublicKeyInfo.getInstance(object)
            );
        }

        return new KeyPair(publicKey, privateKey);
    }
 }